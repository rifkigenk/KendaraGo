# ==========================================================
# 01. PENGUJIAN ALUR PEMESANAN DI BROWSER
# Memeriksa interaksi lokasi dan pesanan dengan Playwright, SQLite sementara, dan hasil pencarian simulasi.
# ==========================================================

"""Run explicitly: python tests/browser_bali_flow.py (requires Playwright + Chrome).

Uses an isolated SQLite database. Provider results are simulated only for UI coverage.
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server

from app import create_app
from config import TestingConfig
from extensions import db
from models import User
from test_rental_flow import rental_data


def run():
    with TemporaryDirectory(prefix="kendarago-browser-") as folder:

        class BrowserConfig(TestingConfig):
            SECRET_KEY = "a" * 64
            WTF_CSRF_SECRET_KEY = "b" * 64
            WTF_CSRF_ENABLED = True
            SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(Path(folder) / "browser.db")
            MAP_TILES_ENABLED = False
            GEOAPIFY_API_KEY = ""
            WHATSAPP_ENABLED = False

        app = create_app(BrowserConfig)
        with app.app_context():
            db.create_all()
            user, vehicle, _, _ = rental_data()
            admin = User.query.filter_by(role="admin").one()
            admin.set_password("Browser-Admin-123!")
            vehicle_id = vehicle.id
            db.session.commit()
        server = make_server("127.0.0.1", 5099, app, threaded=True)
        Thread(target=server.serve_forever, daemon=True).start()
        artifacts = Path("instance/test-artifacts")
        artifacts.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=True)
                customer_ctx = browser.new_context(
                    viewport={"width": 390, "height": 844}
                )
                admin_ctx = browser.new_context(
                    viewport={"width": 1440, "height": 1000}
                )
                customer, admin_page = customer_ctx.new_page(), admin_ctx.new_page()
                errors = []
                for page in [customer, admin_page]:
                    page.on("pageerror", lambda error: errors.append(str(error)))

                def login(page, email, password):
                    page.goto("http://127.0.0.1:5099/auth/login")
                    page.locator("[name=email]").fill(email)
                    page.locator("[name=password]").fill(password)
                    page.get_by_role("button", name="Masuk", exact=True).click()
                    page.wait_for_url(
                        "**/admin/" if email.startswith("admin") else "**/pelanggan/"
                    )

                login(admin_page, "admin@example.com", "Browser-Admin-123!")
                admin_page.goto("http://127.0.0.1:5099/admin/pesanan")
                expect(admin_page.locator("[data-sync-message]")).to_contain_text(
                    "Tersinkron"
                )
                login(customer, "customer@example.com", "Passphrase-Test-123")
                customer.goto(f"http://127.0.0.1:5099/pelanggan/pesan/{vehicle_id}")
                expect(customer.locator("[data-prefix=return]")).to_be_hidden()
                expect(
                    customer.locator("[data-prefix=pickup] [data-search-wrap]")
                ).to_be_hidden()
                customer.locator("[data-prefix=pickup] [data-geolocate]").click()
                expect(
                    customer.locator("[data-prefix=pickup] [data-location-message]")
                ).to_contain_text("manual", timeout=15000)
                # Simulate only the external provider response, not the booking backend.
                app.config["GEOAPIFY_API_KEY"] = "browser-test-only"
                customer.reload()
                result = dict(
                    place_name="Hotel fixture untuk uji browser",
                    street="",
                    building_number="",
                    village="Kelurahan fixture",
                    district="Kecamatan fixture",
                    city="Denpasar",
                    province="Bali",
                    postcode="",
                    latitude=-8.65,
                    longitude=115.216,
                    formatted="Hotel fixture untuk uji browser, Bali",
                )
                customer.route(
                    "**/lokasi/cari?*",
                    lambda route: route.fulfill(
                        content_type="application/json",
                        body=json.dumps({"results": [result]}),
                    ),
                )
                customer.locator("[data-prefix=pickup] [data-search]").fill(
                    "hotel fixture"
                )
                customer.locator("[data-prefix=pickup] [data-results] button").click()
                expect(customer.locator("#pickup-building_number")).to_have_value("")
                expect(customer.locator("#pickup-place_name")).to_have_value(
                    result["place_name"]
                )
                # Office selection still locks the admin's address and pin.
                customer.locator("#pickup-kind").select_option("office")
                customer.locator("#pickup-office").select_option(index=1)
                expect(customer.locator("#pickup-place_name")).to_have_attribute(
                    "readonly", ""
                )
                expect(
                    customer.locator("[data-prefix=pickup] [data-manual]")
                ).to_be_hidden()
                customer.locator("#pickup-kind").select_option("other")
                expect(customer.locator("#pickup-latitude")).to_have_value("")
                # Complete the main flow without a geocoding service or administrative fields.
                app.config["GEOAPIFY_API_KEY"] = ""
                customer.reload()
                customer_ctx.grant_permissions(["geolocation"])
                customer_ctx.set_geolocation(
                    {"latitude": -8.65, "longitude": 115.216, "accuracy": 10}
                )
                customer.locator("[data-prefix=pickup] [data-geolocate]").click()
                expect(customer.locator("#pickup-latitude")).to_have_value("-8.6500000")
                customer.locator("[data-prefix=pickup] [data-map]").click(
                    position={"x": 70, "y": 100}
                )
                customer.locator("#pickup-place_name").fill("Lobi tempat menginap")
                for key in ["village", "district", "city", "postcode"]:
                    expect(customer.locator(f"#pickup-{key}")).to_have_value("")
                customer.locator("#pickup-instructions").fill(
                    "Lobi fixture. "
                    + "Patokan panjang untuk menguji tampilan alamat. " * 5
                )
                customer.locator("#pickup-latitude").fill("-8.651")
                customer.locator("[data-prefix=pickup] [data-confirm-location]").check()
                customer.locator("#pickup-instructions").fill(
                    "Lobi fixture — perubahan harus membatalkan konfirmasi."
                )
                expect(
                    customer.locator("[data-prefix=pickup] [data-confirm-location]")
                ).not_to_be_checked()
                customer.locator("[data-prefix=pickup] [data-confirm-location]").check()
                start = str(date.today() + timedelta(days=2))
                end = str(date.today() + timedelta(days=3))
                customer.locator("[name=start_date]").evaluate(
                    "(el, value) => el._flatpickr.setDate(value, true)", start
                )
                customer.locator("[name=end_date]").evaluate(
                    "(el, value) => el._flatpickr.setDate(value, true)", end
                )
                customer.locator("[name=pickup_time]").fill("10:00")
                customer.locator("#terms").check()
                customer.screenshot(
                    path=str(artifacts / "bali-booking-mobile.png"), full_page=True
                )
                assert customer.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), customer.evaluate(
                    """() =>
                    [...document.querySelectorAll('body *')].filter(el => el.getBoundingClientRect().right > innerWidth)
                    .map(el => [el.tagName, el.className, el.getBoundingClientRect().width]).slice(0, 15)
                """
                )
                customer.locator("[data-booking-form] button[type=submit]").click()
                customer.wait_for_url("**/pelanggan/pesanan/*")
                code = customer.locator("h1").inner_text()
                expect(admin_page.locator("[data-booking-list]")).to_contain_text(
                    code, timeout=10000
                )
                customer.goto(customer.url + "/lokasi")
                expect(customer.locator("[data-same-location]")).to_be_checked()
                expect(customer.locator("[data-prefix=return]")).to_be_hidden()
                customer.locator("#pickup-instructions").fill(
                    "Instruksi baru dari akun penyewa"
                )
                customer.locator("[data-prefix=pickup] [data-confirm-location]").check()
                customer.locator("[data-same-location]").check()
                customer.locator("[data-location-update] button[type=submit]").click()
                customer.wait_for_url("**/pelanggan/pesanan/*")
                expect(customer.locator("[data-live-locations]")).to_contain_text(
                    "Instruksi baru dari akun penyewa"
                )
                admin_page.get_by_role("link", name=code, exact=True).click()
                expect(admin_page.locator("[data-live-locations]")).to_contain_text(
                    "Instruksi baru dari akun penyewa"
                )
                admin_page.locator("#next-status").select_option("Dibatalkan admin")
                admin_page.locator("[data-status-form] button").click()
                expect(customer.locator("[data-live-status]")).to_have_text(
                    "Dibatalkan admin", timeout=10000
                )
                expect(customer.locator(".payment-panel")).to_be_hidden()
                customer_ctx.set_offline(True)
                expect(customer.locator("[data-sync-message]")).to_contain_text(
                    "Koneksi terputus"
                )
                customer_ctx.set_offline(False)
                expect(customer.locator("[data-sync-message]")).to_contain_text(
                    "Tersinkron", timeout=20000
                )
                customer.screenshot(
                    path=str(artifacts / "bali-detail-mobile.png"), full_page=True
                )
                admin_page.screenshot(
                    path=str(artifacts / "bali-admin-detail.png"), full_page=True
                )
                assert not errors, errors
                browser.close()
                print(
                    "Browser PASS: simple map flow without geocoder, office selection, optional search, confirmation, mobile, booking, location edit, admin sync, offline/reconnect; no JavaScript errors."
                )
        finally:
            server.shutdown()
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    run()
