# ==========================================================
# 01. PENGUJIAN IDENTITAS DAN KANTOR UTAMA
# Memeriksa format identitas, pembatasan tampilan nomor, penyimpanan pesanan, dan pemilihan kantor.
# ==========================================================

"""Identity persistence/privacy, one-office selection and map policy regression tests."""

import pytest

from extensions import db
from models import AppSetting, Location, Rental, User
from services.identity_service import normalize_booking_phone, validate_identity
from services.location_service import validate_address
from test_bali_locations import address, booking_form, login, fresh_request_user
from test_rental_flow import rental_data


@pytest.mark.parametrize(
    "kind,number,country",
    [
        ("NIK", "123", ""),
        ("NIK", "123456789012345a", ""),
        ("NISN", "12345678901", ""),
        ("PASSPORT", "A12", "Australia"),
        ("PASSPORT", "A1234567", ""),
        ("PASSPORT", "<script>", "Australia"),
        ("UNKNOWN", "1234567890123456", ""),
    ],
)
def test_invalid_identity(kind, number, country):
    with pytest.raises(ValueError):
        validate_identity(kind, number, country)


@pytest.mark.parametrize(
    "kind,number,country,phone",
    [
        ("NIK", "0123456789012345", "Indonesia", "081234567890"),
        ("NISN", "0123456789", "Indonesia", "081234567890"),
        ("PASSPORT", "AB1234567", "Australia", "+61 412 345 678"),
    ],
)
def test_guest_identity_stored_and_scoped(app, client, kind, number, country, phone):
    _, vehicle, _, _ = rental_data()
    vehicle_id = vehicle.id
    form = {
        **booking_form(),
        "full_name": "Penyewa Fixture",
        "phone": phone,
        "identity_type": kind,
        "identity_number": number,
        "identity_country": country,
    }
    response = client.post(f"/kendaraan/{vehicle_id}/pesan", data=form)
    assert response.status_code == 201, response.json
    rental_id, detail_url = response.json["id"], response.json["url"]
    db.session.remove()
    rental = db.session.get(Rental, rental_id)
    assert (rental.identity_type, rental.identity_number, rental.identity_country) == (
        kind,
        number,
        country,
    )
    assert rental.customer_phone == normalize_booking_phone(phone)
    assert (
        client.post(f"/kendaraan/{vehicle_id}/pesan", data=form).json["id"] == rental_id
    )
    assert Rental.query.count() == 1
    assert (
        client.post(
            f"/kendaraan/{vehicle_id}/pesan",
            data={**form, "identity_number": "changed"},
        ).status_code
        == 409
    )
    page = client.get(detail_url)
    assert page.status_code == 200
    assert rental.masked_identity_number in page.text
    assert number not in page.text
    assert number not in client.get("/api/pesanan").text
    assert number not in client.get(f"/api/pesanan/{rental_id}").text
    assert app.test_client().get(detail_url).status_code == 404
    for role in ["admin", "petugas"]:
        user = User.query.filter_by(role=role).first()
        if not user:
            user = User(name="Petugas Fixture", email="staff@example.com", role=role)
            user.set_password("Fixture-Password-123!")
            db.session.add(user)
            db.session.commit()
        authorized = app.test_client()
        login(authorized, user)
        detail = authorized.get(f"/api/pesanan/{rental_id}/admin")
        assert detail.status_code == 200
        assert number in detail.text


def test_missing_identity_rejected_and_form_preserved(app, client):
    _, vehicle, _, _ = rental_data()
    form = {
        **booking_form(),
        "full_name": "Penyewa Fixture",
        "phone": "081234567890",
        "identity_number": "bad",
        "response_mode": "html",
    }
    response = client.post(f"/kendaraan/{vehicle.id}/pesan", data=form)
    assert response.status_code == 422
    assert 'value="bad"' in response.text
    assert 'value="Penyewa Fixture"' in response.text
    assert Rental.query.count() == 0


def test_only_primary_office_is_managed_and_bookable(app, client):
    _, _, primary, _ = rental_data()
    primary.name = "Denpasar"
    old = Location(name="Ambon", address="Alamat arsip")
    secondary = Location(
        name="Kantor lain di Bali",
        address="Alamat arsip",
        address_data=address(),
        verified_by_id=primary.verified_by_id,
    )
    db.session.add_all([old, secondary])
    db.session.commit()
    assert [o["id"] for o in client.get("/lokasi/kantor").json["offices"]] == [
        primary.id
    ]
    with pytest.raises(ValueError, match="Kantor"):
        validate_address(
            {
                **address(),
                "kind": "office",
                "office_id": secondary.id,
                "office_updated_at": secondary.updated_at.isoformat(),
            }
        )
    login(client, User.query.filter_by(role="admin").one())
    page = client.get("/lokasi/admin")
    assert page.status_code == 200
    assert "Denpasar" in page.text
    assert "Ambon" not in page.text
    assert "Kantor lain di Bali" not in page.text
    assert "Kantor baru" not in page.text
    payload = {
        "id": primary.id,
        "version": primary.updated_at.isoformat(),
        "active": True,
        "address": {**address(), "kind": "office", "place_name": "KendaraGo Denpasar"},
    }
    assert (
        client.post("/lokasi/admin", json={**payload, "id": secondary.id}).status_code
        == 422
    )
    assert client.post("/lokasi/admin", json=payload).status_code == 200
    assert Location.query.count() == 3
    assert AppSetting.query.filter_by(
        setting_key="primary_office_id"
    ).one().setting_value == str(primary.id)
    assert [o["id"] for o in client.get("/lokasi/kantor").json["offices"]] == [
        primary.id
    ]
    assert client.post("/lokasi/admin", json=payload).status_code == 409


def test_map_referrer_policy_and_google_allowlist(app, client):
    app.config["GOOGLE_MAPS_API_KEY"] = ""
    page = client.get("/")
    assert page.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "unsafe-eval" not in page.headers["Content-Security-Policy"]
    app.config["GOOGLE_MAPS_API_KEY"] = "fixture-key-not-a-real-key"
    page = client.get("/")
    assert "https://maps.googleapis.com" in page.headers["Content-Security-Policy"]
    assert "https://*.googleapis.com" in page.headers["Content-Security-Policy"]
    assert "https://*.gstatic.com" in page.headers["Content-Security-Policy"]
