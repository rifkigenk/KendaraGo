"""Integration coverage for address confirmation, durable bookings, ownership and sync."""

import json
from datetime import date, timedelta
from uuid import uuid4

import pytest
from flask import g

from extensions import db
from models import Location, Rental, User
from services.location_service import in_bali, validate_address
from test_rental_flow import rental_data


@pytest.fixture(autouse=True)
def fresh_request_user(app):
    # The shared fixture keeps an app context open; real HTTP requests do not.
    @app.before_request
    def reset_cached_user():
        g.pop("_login_user", None)


def address(**overrides):
    # Synthetic test data only; never seeded into the application database.
    return dict(
        kind="hotel",
        confirmed=True,
        place_name="Titik temu fixture pengujian",
        street="",
        building_number="",
        village="Kelurahan fixture",
        district="Kecamatan fixture",
        city="Denpasar",
        province="Bali",
        postcode="",
        latitude=-8.65,
        longitude=115.216,
        instructions="Lobi fixture",
        **overrides,
    )


def login(client, user):
    user.set_password("Test-Login-123!")
    db.session.commit()
    with client.session_transaction() as session:
        session.clear()
    result = client.post(
        "/auth/login", data={"email": user.email, "password": "Test-Login-123!"}
    )
    assert result.status_code == 302


def booking_form():
    return dict(
        request_key=str(uuid4()),
        start_date=str(date.today() + timedelta(days=2)),
        end_date=str(date.today() + timedelta(days=3)),
        pickup_time="09:00",
        terms="1",
        pickup_address=json.dumps(address()),
        same_location="1",
        notes="Catatan fixture",
    )


@pytest.mark.parametrize(
    "lat,lon",
    [
        (-6.2, 106.8),
        (-8.4, 114.1),
        (-8.6, 116.1),
        (-8.7, 114.9),
        (float("nan"), 115),
        (-8, float("inf")),
    ],
)
def test_polygon_rejects_outside_and_nonfinite(lat, lon):
    assert not in_bali(lat, lon)


@pytest.mark.parametrize(
    "lat,lon",
    [(-8.65, 115.216), (-8.748, 115.166), (-8.724, 115.544), (-8.678, 115.45)],
)
def test_bali_and_islands_are_supported(lat, lon):
    assert in_bali(lat, lon)


def test_no_fabricated_optional_address_fields(app):
    result = validate_address(address())
    assert result["building_number"] == result["postcode"] == ""
    with pytest.raises(ValueError, match="konfirmasi"):
        validate_address({**address(), "confirmed": False})
    with pytest.raises(ValueError, match="Bali"):
        validate_address({**address(), "latitude": -6.2, "longitude": 106.8})


def test_simple_meeting_point_booking_and_edit(app, client):
    user, vehicle, _, _ = rental_data()
    login(client, user)
    point = dict(
        kind="other",
        confirmed=True,
        place_name="Lobi tempat menginap",
        province="Bali",
        latitude=-8.65,
        longitude=115.216,
    )
    form = {**booking_form(), "pickup_address": json.dumps(point)}
    response = client.post(f"/pelanggan/pesan/{vehicle.id}", data=form)
    assert response.status_code == 201, response.json
    rental = db.session.get(Rental, response.json["id"])
    assert rental.pickup_address == rental.return_address
    assert rental.pickup_address["formatted"] == "Lobi tempat menginap, Bali"
    assert all(
        rental.pickup_address[key] == ""
        for key in ["village", "district", "city", "postcode"]
    )
    response = client.post(
        f"/api/pesanan/{rental.id}/lokasi",
        json={
            "version": rental.updated_at.isoformat(),
            "pickup_address": point,
            "return_address": {
                **point,
                "place_name": "Pintu utama",
                "latitude": -8.651,
            },
            "same_location": False,
            "notes": "",
        },
    )
    assert response.status_code == 200, response.json
    db.session.refresh(rental)
    assert rental.return_address["place_name"] == "Pintu utama"
    assert rental.pickup_address["place_name"] == point["place_name"]
    for invalid in [
        {**point, "place_name": " "},
        {**point, "latitude": ""},
        {**point, "confirmed": False},
        {**point, "latitude": -6.2},
    ]:
        with pytest.raises(ValueError):
            validate_address(invalid)


def test_booking_admin_sync_status_and_owner_security(app, client):
    user, vehicle, _, _ = rental_data()
    admin = User.query.filter_by(role="admin").one()
    customer_id, admin_id, vehicle_id = user.id, admin.id, vehicle.id
    admin_client = app.test_client()
    login(client, user)
    form = booking_form()
    created = client.post(f"/pelanggan/pesan/{vehicle_id}", data=form)
    assert created.status_code == 201, created.json
    rental_id = created.json["id"]
    retry = client.post(f"/pelanggan/pesan/{vehicle_id}", data=form)
    assert retry.status_code == 200
    assert retry.json["id"] == rental_id
    assert Rental.query.count() == 1
    assert (
        client.post(
            f"/pelanggan/pesan/{vehicle_id}", data={**form, "notes": "changed"}
        ).status_code
        == 409
    )
    # Read through a fresh ORM session to prove the write was committed.
    db.session.remove()
    saved = db.session.get(Rental, rental_id)
    assert saved.customer_id == customer_id
    assert saved.pickup_address == saved.return_address
    assert saved.pickup_address["building_number"] == ""
    login(admin_client, db.session.get(User, admin_id))
    feed = admin_client.get("/api/pesanan")
    assert feed.status_code == 200
    assert feed.json["rentals"][0]["id"] == rental_id
    assert saved.booking_code in feed.json["html"]
    detail = client.get(f"/api/pesanan/{rental_id}").json
    update = client.post(
        f"/api/pesanan/{rental_id}/lokasi",
        json={
            "version": detail["updated_at"],
            "pickup_address": address(),
            "return_address": {
                **address(),
                "kind": "airport",
                "instructions": "Pintu fixture",
            },
            "same_location": False,
            "notes": "Catatan diperbarui",
        },
    )
    assert update.status_code == 200, update.json
    admin_detail = admin_client.get(f"/api/pesanan/{rental_id}").json
    assert admin_detail["return_address"]["instructions"] == "Pintu fixture"
    assert admin_detail["status"] == "Menunggu persetujuan"
    approved = admin_client.post(
        f"/api/pesanan/{rental_id}/status",
        json={"version": admin_detail["updated_at"], "status": "Menunggu pembayaran"},
    )
    assert approved.status_code == 200, approved.json
    admin_detail = admin_client.get(f"/api/pesanan/{rental_id}").json
    assert admin_detail["status"] == "Menunggu pembayaran"
    changed = admin_client.post(
        f"/api/pesanan/{rental_id}/status",
        json={"version": admin_detail["updated_at"], "status": "Dibatalkan admin"},
    )
    assert changed.status_code == 200
    assert client.get(f"/api/pesanan/{rental_id}").json["status"] == "Dibatalkan admin"
    assert (
        client.post(
            f"/api/pesanan/{rental_id}/status", json={"status": "Selesai"}
        ).status_code
        == 403
    )
    other = User(
        name="Other",
        email="other@example.com",
        role="pelanggan",
        password_hash="unused",
    )
    db.session.add(other)
    db.session.commit()
    login(client, other)
    assert client.get("/api/pesanan").json["rentals"] == []
    for path in [
        f"/api/pesanan/{rental_id}",
        f"/pelanggan/pesanan/{rental_id}",
        f"/pelanggan/pesanan/{rental_id}/lokasi",
    ]:
        assert client.get(path).status_code == 404
    assert client.post(f"/api/pesanan/{rental_id}/lokasi", json={}).status_code == 404
    assert "no-store" in feed.headers["Cache-Control"]


def test_office_requires_admin_and_preserves_snapshot(app, client):
    user, vehicle, office, _ = rental_data()
    login(client, user)
    assert client.post("/lokasi/admin", json={}).status_code == 403
    legacy = Location(name="Legacy outside Bali", address="Alamat lama")
    db.session.add(legacy)
    db.session.commit()
    options = client.get("/lokasi/kantor").json["offices"]
    assert [o["id"] for o in options] == [office.id]
    payload = {
        **address(),
        "kind": "office",
        "office_id": office.id,
        "office_updated_at": office.updated_at.isoformat(),
        "place_name": "Client forged name",
    }
    snapshot = validate_address(payload)
    assert snapshot["place_name"] == office.address_data["place_name"]
    form = {**booking_form(), "pickup_address": json.dumps(payload)}
    response = client.post(f"/pelanggan/pesan/{vehicle.id}", data=form)
    assert response.status_code == 201
    saved = db.session.get(Rental, response.json["id"])
    office.address_data = {**office.address_data, "place_name": "Changed office"}
    db.session.commit()
    assert saved.pickup_address["place_name"] != office.address_data["place_name"]
    with pytest.raises(ValueError, match="diperbarui"):
        validate_address(payload)


def test_guest_booking_ownership_retry_and_approval(app, client):
    _, vehicle, _, _ = rental_data()
    form = {**booking_form(), "full_name": "Tamu Fixture", "phone": "081234567890"}
    created = client.post(f"/kendaraan/{vehicle.id}/pesan", data=form)
    assert created.status_code == 201, created.json
    rental_id = created.json["id"]
    saved = db.session.get(Rental, rental_id)
    assert saved.customer_id is None
    assert saved.customer_name == form["full_name"]
    assert saved.customer_phone == form["phone"]
    assert saved.status == "Menunggu persetujuan"
    assert client.get(created.json["url"]).status_code == 200
    assert client.get("/pesanan").status_code == 200
    assert client.get("/api/pesanan").json["rentals"][0]["id"] == rental_id
    retry = client.post(f"/kendaraan/{vehicle.id}/pesan", data=form)
    assert retry.status_code == 200
    assert retry.json["id"] == rental_id
    assert Rental.query.count() == 1
    assert (
        client.post(
            f"/api/pesanan/{rental_id}/status", json={"status": "Menunggu pembayaran"}
        ).status_code
        == 401
    )

    other = app.test_client()
    assert other.get(created.json["url"]).status_code == 404
    assert other.get(f"/api/pesanan/{rental_id}").status_code == 401
    assert other.get(f"/kendaraan/{vehicle.id}/pesan").status_code == 200
    assert other.get(f"/api/pesanan/{rental_id}").status_code == 404
    assert other.get("/api/pesanan").json["rentals"] == []

    admin_client = app.test_client()
    login(admin_client, User.query.filter_by(role="admin").one())
    detail = admin_client.get(f"/api/pesanan/{rental_id}").json
    response = admin_client.post(
        f"/api/pesanan/{rental_id}/status",
        json={"version": detail["updated_at"], "status": "Menunggu pembayaran"},
    )
    assert response.status_code == 200, response.json
    assert (
        client.get(f"/api/pesanan/{rental_id}").json["status"] == "Menunggu pembayaran"
    )


def test_geocoder_fallback_and_anonymous_api(app, client, monkeypatch):
    assert client.get("/api/pesanan").status_code == 401
    app.config["GEOAPIFY_API_KEY"] = ""
    monkeypatch.setattr(
        "routes.locations.photon_results",
        lambda *args: [
            {
                "geometry": {"coordinates": [115.216, -8.65]},
                "properties": {"name": "Hotel fixture", "city": "Denpasar"},
            }
        ],
    )
    response = client.get("/lokasi/cari?q=hotel")
    assert response.status_code == 200
    assert response.json["results"][0]["place_name"] == "Hotel fixture"
    assert client.get("/lokasi/admin").status_code == 401

    def unavailable(*args):
        raise TimeoutError()

    monkeypatch.setattr("routes.locations.photon_results", unavailable)
    response = client.get("/lokasi/cari?q=hotel")
    assert response.status_code == 503
    assert "manual" in response.json["error"]
    user, _, _, _ = rental_data()
    login(client, user)
    response = client.get("/lokasi/cari?q=hotel")
    assert response.status_code == 503
    assert "manual" in response.json["error"]


def test_csrf_and_rendered_pages(app, client):
    user, vehicle, _, _ = rental_data()
    login(client, user)
    page = client.get(f"/pelanggan/pesan/{vehicle.id}")
    assert page.status_code == 200
    assert b"Lokasi Pengambilan" in page.data and b"Lokasi Pengembalian" in page.data
    assert "geolocation=(self)" in page.headers["Permissions-Policy"]
    assert b"watchPosition" not in page.data
    made = client.post(f"/pelanggan/pesan/{vehicle.id}", data=booking_form())
    assert client.get(made.json["url"]).status_code == 200
    assert client.get(made.json["url"] + "/lokasi").status_code == 200
    assert client.get("/pelanggan/").status_code == 200
    app.config["WTF_CSRF_ENABLED"] = True
    assert (
        client.post(f"/pelanggan/pesan/{vehicle.id}", data=booking_form()).status_code
        == 400
    )
    assert (
        client.post(f"/api/pesanan/{made.json['id']}/lokasi", json={}).status_code
        == 400
    )
    app.config["WTF_CSRF_ENABLED"] = False
    login(client, User.query.filter_by(role="admin").one())
    for path in [
        "/admin/",
        "/admin/pesanan",
        "/lokasi/admin",
        f"/api/pesanan/{made.json['id']}/admin",
    ]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
