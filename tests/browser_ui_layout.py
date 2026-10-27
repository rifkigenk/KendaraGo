"""Responsive UI regression checks using isolated data, Playwright and Chrome.

Run explicitly: python tests/browser_ui_layout.py
"""

import base64
import json
import sys
from datetime import date, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import create_app
from config import TestingConfig
from extensions import db
from models import User
from services.rental_service import create_rental
from test_rental_flow import rental_data


def run():
    artifacts = Path("instance/test-artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    failures = []
    checked = 0
    with TemporaryDirectory(prefix="kendarago-ui-") as folder:

        class BrowserConfig(TestingConfig):
            SECRET_KEY = "a" * 64
            WTF_CSRF_SECRET_KEY = "b" * 64
            SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(Path(folder) / "ui.db")
            WHATSAPP_ENABLED = False
            MAP_TILES_ENABLED = True

        app = create_app(BrowserConfig)
        with app.app_context():
            db.create_all()
            customer, vehicle, office, _ = rental_data()
            admin = User.query.filter_by(role="admin").one()
            staff = User(
                name="Petugas KendaraGo", email="staff@example.com", role="petugas"
            )
            for user in [customer, admin, staff]:
                user.set_password("Browser-Test-123!")
            db.session.add(staff)
            db.session.commit()
            rental_ids = []
            for index, status in enumerate(
                ["Menunggu persetujuan", "Dikonfirmasi", "Sedang disewa"]
            ):
                start = date.today() + timedelta(days=3 + index * 10)
                rental = create_rental(
                    customer,
                    vehicle,
                    start,
                    start + timedelta(days=1),
                    time(9),
                    office.id,
                    office.id,
                )
                rental.status = status
                rental.pickup_address = {
                    **office.address_data,
                    "formatted": "Kantor fixture, Denpasar, Bali",
                }
                rental.return_address = rental.pickup_address.copy()
                if status == "Dikonfirmasi":
                    rental.start_date = date.today()
                if status == "Sedang disewa":
                    rental.start_date = date.today() - timedelta(days=1)
                    rental.end_date = date.today()
                db.session.commit()
                rental_ids.append(rental.id)
            vehicle_id = vehicle.id
        paths = {
            "public": [
                "/",
                "/kendaraan",
                f"/kendaraan/{vehicle_id}",
                f"/kendaraan/{vehicle_id}/pesan",
                "/auth/login",
                "/auth/register",
                "/pesanan",
            ],
            "admin": [
                "/admin/",
                "/admin/pesanan",
                "/admin/kendaraan",
                "/admin/kendaraan/tambah",
                "/admin/pembayaran",
                "/admin/pelanggan/verifikasi",
                "/lokasi/admin",
                f"/api/pesanan/{rental_ids[0]}/admin",
            ],
            "staff": [
                "/petugas/",
                f"/api/pesanan/{rental_ids[0]}/admin",
                f"/petugas/pengambilan/{rental_ids[1]}",
                f"/petugas/pengembalian/{rental_ids[2]}",
            ],
            "customer": [
                "/pelanggan/",
                "/pelanggan/profil",
                f"/pelanggan/pesanan/{rental_ids[0]}",
                f"/pelanggan/pesanan/{rental_ids[0]}/lokasi",
                "/auth/ubah-password",
            ],
        }
        server = make_server("127.0.0.1", 0, app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        tile = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
        )
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=True)
                for width in (1440, 768, 390):
                    for role, urls in paths.items():
                        context = browser.new_context(
                            viewport={"width": width, "height": 960}
                        )
                        context.route(
                            "https://tile.openstreetmap.org/**",
                            lambda route: route.fulfill(
                                content_type="image/png", body=tile
                            ),
                        )
                        page = context.new_page()
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        if role != "public":
                            page.goto(base + "/auth/login")
                            page.locator("[name=email]").fill(f"{role}@example.com")
                            page.locator("[name=password]").fill("Browser-Test-123!")
                            page.get_by_role("button", name="Masuk", exact=True).click()
                            page.wait_for_url(
                                "**/admin/"
                                if role == "admin"
                                else (
                                    "**/petugas/"
                                    if role == "staff"
                                    else "**/pelanggan/"
                                )
                            )
                        for path in urls:
                            errors.clear()
                            response = page.goto(base + path)
                            assert response.status == 200, (path, response.status)
                            if page.locator("[data-booking-feed]").count():
                                expect(
                                    page.locator("[data-booking-list]")
                                ).to_have_attribute("aria-busy", "false")
                            page.locator(".footer").scroll_into_view_if_needed()
                            page.evaluate("() => window.scrollTo(0, 0)")
                            issues = page.evaluate(
                                """() => {
                              const issues = [];
                              const footer = document.querySelector('footer').getBoundingClientRect();
                              const shell = document.querySelector('.dashboard-content');
                              if (shell) {
                                const children = [...shell.children].filter(el => !el.hidden);
                                for (const el of children) {
                                  if (el.getBoundingClientRect().bottom > footer.top + 2) issues.push('content overlaps footer: ' + el.className);
                                }
                              }
                              for (const el of document.querySelectorAll('main h1, main .btn, .booking-card, .location-editor, [data-map], .dashboard-content, .stat-card')) {
                                if (!el.getClientRects().length || el.closest('[hidden],.table-responsive,.sidebar-nav')) continue;
                                const r = el.getBoundingClientRect();
                                if (r.width && (r.left < -2 || r.right > innerWidth + 2)) issues.push('outside viewport: ' + el.tagName + '.' + el.className);
                              }
                              return issues;
                            }"""
                            )
                            if path == "/petugas/":
                                heading = page.locator("h1").bounding_box()
                                assert heading["y"] < 260, heading
                                search = page.locator("[data-booking-search]")
                                search.fill("no-matching-booking")
                                expect(
                                    page.locator("[data-booking-empty]")
                                ).to_be_visible()
                                search.fill("")
                                page.locator("[data-booking-filter]").select_option(
                                    "all"
                                )
                                expect(
                                    page.locator("[data-booking-card]:visible")
                                ).to_have_count(3)
                                page.screenshot(
                                    path=str(artifacts / f"staff-layout-{width}.png"),
                                    full_page=True,
                                )
                            if issues or errors:
                                failures.append(
                                    {
                                        "width": width,
                                        "role": role,
                                        "path": path,
                                        "issues": issues,
                                        "errors": errors.copy(),
                                    }
                                )
                                page.screenshot(
                                    path=str(
                                        artifacts / f"ui-failure-{width}-{checked}.png"
                                    ),
                                    full_page=True,
                                )
                            checked += 1
                        context.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
    print(json.dumps({"pages_checked": checked, "failures": failures}, indent=2))
    assert not failures


if __name__ == "__main__":
    run()
