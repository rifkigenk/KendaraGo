# ==========================================================
# 01. PENGUJIAN PEMUATAN PETA DI BROWSER
# Memeriksa integrasi dan status pemuatan peta memakai tile serta SDK simulasi, bukan kredensial Google aktif.
# ==========================================================

"""Run: python tests/browser_map_loading.py (Playwright + Chrome).

Tests real browser integration with simulated OSM tiles / Google SDK contracts.
This cannot verify a live Google Cloud key, billing, or coverage.
"""

import base64
import sys
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import create_app
from config import TestingConfig
from extensions import db
from test_rental_flow import rental_data


def run():
    with TemporaryDirectory(prefix="kendarago-map-") as folder:

        class BrowserConfig(TestingConfig):
            SECRET_KEY = "a" * 64
            WTF_CSRF_SECRET_KEY = "b" * 64
            SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(Path(folder) / "maps.db")
            MAP_TILES_ENABLED = True
            GOOGLE_MAPS_API_KEY = ""
            WHATSAPP_ENABLED = False

        app = create_app(BrowserConfig)
        with app.app_context():
            db.create_all()
            _, vehicle, _, _ = rental_data()
            vehicle_id = vehicle.id
        server = make_server("127.0.0.1", 0, app, threaded=True)
        Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        url = f"{base}/kendaraan/{vehicle_id}/pesan"
        tile = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
        )
        sdk = (Path(__file__).parent / "fixtures/google_maps_stub.js").read_text(
            encoding="utf-8"
        )
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=True)
                for width in (1280, 390):
                    page = browser.new_page(
                        viewport={"width": width, "height": 900},
                        reduced_motion="reduce",
                    )
                    errors, requests, referrers = [], [], []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("request", lambda request: requests.append(request.url))

                    def serve_tile(route):
                        referrers.append(route.request.headers.get("referer"))
                        route.fulfill(content_type="image/png", body=tile)

                    page.route("https://tile.openstreetmap.org/**", serve_tile)
                    response = page.goto(url)
                    assert (
                        response.headers["referrer-policy"]
                        == "strict-origin-when-cross-origin"
                    )
                    pickup = page.locator('[data-prefix="pickup"] [data-map]')
                    dropoff = page.locator('[data-prefix="return"] [data-map]')
                    button = page.locator('[data-prefix="pickup"] [data-map-3d]')
                    expect(pickup).to_have_attribute("data-map-ready", "true")
                    expect(button).to_be_hidden()
                    assert referrers and all(value == base + "/" for value in referrers)
                    assert not any(
                        "googleapis" in r or "maplibre" in r or "openfreemap" in r
                        for r in requests
                    )
                    assert dropoff.evaluate("el => !el._meetingMap.engine")
                    assert (
                        pickup.evaluate("el => el._meetingMap.engine.getZoom()") == 12
                    )
                    pickup.click(position={"x": 100, "y": 100})
                    expect(page.locator("#pickup-latitude")).not_to_have_value("")
                    expect(pickup.locator(".meeting-pin")).to_have_count(1)
                    page.locator("[data-same-location]").uncheck()
                    expect(dropoff).to_have_attribute("data-map-engine", "2d")

                    page.unroute("https://tile.openstreetmap.org/**")
                    page.route(
                        "https://tile.openstreetmap.org/**", lambda route: route.abort()
                    )
                    page.reload()
                    expect(pickup).to_have_attribute("data-map-state", "error")
                    page.unroute("https://tile.openstreetmap.org/**")
                    page.route("https://tile.openstreetmap.org/**", serve_tile)
                    page.locator(
                        '[data-prefix="pickup"] .meeting-map-state button'
                    ).click()
                    expect(pickup).to_have_attribute("data-map-state", "ready")

                    # Complete the actual HTML booking path with a foreign passport.
                    page.locator('[name="full_name"]').fill("Tourist Fixture")
                    page.locator('[name="phone"]').fill("+61 412 345 678")
                    page.locator('[name="identity_type"]').select_option("PASSPORT")
                    page.locator('[name="identity_number"]').fill("AB1234567")
                    page.locator('[name="identity_country"]').fill("Australia")
                    for name, days in [("start_date", 2), ("end_date", 3)]:
                        page.locator(f'[name="{name}"]').evaluate(
                            "(el, value) => el._flatpickr.setDate(value, true)",
                            str(date.today() + timedelta(days=days)),
                        )
                    page.locator('[name="pickup_time"]').fill("10:00")
                    pickup.click(position={"x": 100, "y": 100})
                    page.locator("#pickup-place_name").fill("Lobby fixture Bali")
                    page.locator(
                        '[data-prefix="pickup"] [data-confirm-location]'
                    ).check()
                    page.locator('[name="terms"]').check()
                    page.get_by_role("button", name="Buat pesanan", exact=True).click()
                    page.wait_for_url("**/pesanan/*")
                    expect(
                        page.locator('[aria-label="Identitas penyewa"]')
                    ).to_contain_text("Australia")
                    expect(
                        page.locator('[aria-label="Identitas penyewa"]')
                    ).to_contain_text("*****4567")
                    assert "AB1234567" not in page.content()
                    assert not errors, errors
                    page.close()
                    print(
                        f"PASS {width}px: referrer, 2D retry, deferred maps, passport booking"
                    )

                # Google SDK is intercepted: tests our adapter, not Google's account/service.
                app.config["GOOGLE_MAPS_API_KEY"] = "test-key-not-a-real-key"
                page = browser.new_page()
                errors, sdk_requests = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def serve_sdk(route):
                    sdk_requests.append(route.request.url)
                    route.fulfill(content_type="text/javascript", body=sdk)

                page.route("https://maps.googleapis.com/maps/api/js?*", serve_sdk)
                page.goto(url)
                pickup = page.locator('[data-prefix="pickup"] [data-map]')
                button = page.locator('[data-prefix="pickup"] [data-map-3d]')
                expect(pickup).to_have_attribute("data-map-ready", "true")
                expect(pickup).to_have_attribute("data-map-engine", "google")
                page.locator("[data-same-location]").uncheck()
                expect(
                    page.locator('[data-prefix="return"] [data-map]')
                ).to_have_attribute("data-map-ready", "true")
                assert len(sdk_requests) == 1
                page.evaluate(
                    "() => testGoogleMaps[0].emit('click', {latLng:{lat:()=>-8.65,lng:()=>115.216}})"
                )
                expect(page.locator("#pickup-latitude")).to_have_value("-8.6500000")
                button.click()
                expect(button).to_have_text("Gunakan 2D")
                assert pickup.evaluate("el => el._meetingMap.is3D")
                button.click()
                expect(button).to_have_text("Lihat 3D")
                assert page.evaluate("() => testGoogleMarkers[0].position.lat") == -8.65
                pickup.evaluate("el => el._meetingMap.setLocked(true)")
                assert page.evaluate("() => testGoogleMarkers[0].gmpDraggable") is False
                page.evaluate("() => gm_authFailure()")
                expect(pickup).to_have_attribute("data-map-state", "error")
                expect(button).to_be_disabled()
                assert not errors, errors
                browser.close()
                print(
                    "PASS Google SDK contract: one loader, 2D/3D, pin, lock, auth failure (simulated)"
                )
        finally:
            server.shutdown()
            server.server_close()
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    run()
