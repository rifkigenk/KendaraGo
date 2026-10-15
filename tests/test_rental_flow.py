# ==========================================================
# 01. PENGUJIAN ALUR PENYEWAAN
# Memeriksa bentrok jadwal, pembatalan, pelepasan kuota promo, tenggat, dan kode pesanan.
# ==========================================================

from datetime import date, time, timedelta
from decimal import Decimal

import pytest

from extensions import db
from models import (
    Category,
    CustomerProfile,
    Location,
    Payment,
    Promotion,
    PromotionUsage,
    Rental,
    RentalStatusLog,
    User,
    Vehicle,
)
from services.payment_service import create_payment
from services.rental_service import (
    cancel_rental,
    create_rental,
    expire_unpaid_rentals,
    utc_now,
)


# Membuat pelanggan, kendaraan, lokasi, dan promo untuk skenario pengujian.
def rental_data():
    user = User(
        name="Pelanggan Test",
        email="customer@example.com",
        phone="081234567891",
        role="pelanggan",
    )
    user.set_password("Passphrase-Test-123")
    user.profile = CustomerProfile(verification_status="Terverifikasi")
    category = Category(
        name="Mobil Test", vehicle_type="Mobil", late_fee_per_day=100000
    )
    location = Location(name="Cabang Test", address="Alamat test")
    vehicle = Vehicle(
        code="TEST-001",
        category=category,
        location=location,
        name="Kendaraan Test",
        brand="Test",
        license_plate="B 1000 TST",
        production_year=2026,
        transmission="Otomatis",
        fuel_type="Bensin",
        daily_price=Decimal("300000"),
        deposit=Decimal("500000"),
        status="Tersedia",
        is_active=True,
    )
    today = date.today()
    promotion = Promotion(
        code="HEMAT",
        name="Promo Test",
        discount_type="Nominal",
        discount_value=Decimal("50000"),
        minimum_transaction=Decimal("0"),
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=30),
        quota=1,
        is_active=True,
    )
    db.session.add_all([user, category, location, vehicle, promotion])
    db.session.commit()
    return user, vehicle, location, promotion


# Membuat transaksi uji dengan jadwal mendatang dan promo opsional.
def test_public_rental_opens_whatsapp_without_external_post_redirect(app, client):
    from html import unescape
    import re
    from urllib.parse import parse_qs, urlsplit

    _, vehicle, location, _ = rental_data()
    app.config["WHATSAPP_ENABLED"] = False
    app.config["WHATSAPP_NUMBER"] = "6282282026127"
    form = {
        "full_name": "Pelanggan Demo",
        "nik": "1234567890123456",
        "whatsapp": "081234567890",
        "emergency_phone": "081234567899",
        "start_date": str(date.today() + timedelta(days=2)),
        "end_date": str(date.today() + timedelta(days=3)),
        "pickup_time": "09:00",
        "pickup_location_id": str(location.id),
        "sim_type": "A",
        "sim_number": "123456789012",
        "terms": "1",
    }
    response = client.post(f"/kendaraan/{vehicle.id}/pesan", data=form)
    assert response.status_code == 200
    assert "Location" not in response.headers
    html = response.get_data(as_text=True)
    link = unescape(re.search(r'id="open-whatsapp"[^>]+href="([^"]+)"', html)[1])
    target = urlsplit(link)
    assert target.netloc == "wa.me"
    assert target.path == "/6282282026127"
    message = parse_qs(target.query)["text"][0]
    assert "Pelanggan Demo" in message
    assert "1234567890123456" not in message
    nonce = re.search(r'<script nonce="([^"]+)"', html)[1]
    assert f"'nonce-{nonce}'" in response.headers["Content-Security-Policy"]
    assert "window.location.replace" in html
    form["nik"] = "123"
    invalid = client.post(f"/kendaraan/{vehicle.id}/pesan", data=form)
    assert b'id="rental-form-error"' in invalid.data
    assert b'id="open-whatsapp"' not in invalid.data


def make_rental(user, vehicle, location, promo="HEMAT"):
    start = date.today() + timedelta(days=2)
    return create_rental(
        user,
        vehicle,
        start,
        start + timedelta(days=1),
        time(9, 0),
        location.id,
        location.id,
        promo_code=promo,
    )


# Memastikan reservasi memblokir jadwal bentrok dan pembatalan melepas kuota promo.
def test_booking_blocks_overlap_and_cancel_releases_promo(app):
    user, vehicle, location, _ = rental_data()
    rental = make_rental(user, vehicle, location)

    assert PromotionUsage.query.filter_by(rental_id=rental.id).count() == 1
    with pytest.raises(ValueError, match="tidak tersedia"):
        make_rental(user, vehicle, location, promo=None)

    cancel_rental(rental, user)
    db.session.commit()

    assert rental.status == "Dibatalkan pelanggan"
    assert PromotionUsage.query.filter_by(rental_id=rental.id).count() == 0
    assert RentalStatusLog.query.filter_by(
        rental_id=rental.id, new_status="Dibatalkan pelanggan"
    ).first()
    assert make_rental(user, vehicle, location).id != rental.id


# Memastikan transaksi kedaluwarsa dibatalkan dan kuota promo dikembalikan.
def test_expiration_cancels_booking_and_releases_quota(app):
    user, vehicle, location, _ = rental_data()
    rental = make_rental(user, vehicle, location)
    rental.payment_due_at = utc_now() - timedelta(seconds=1)
    db.session.commit()

    assert expire_unpaid_rentals() == 1
    assert rental.status == "Dibatalkan otomatis"
    assert PromotionUsage.query.filter_by(rental_id=rental.id).count() == 0


# Memastikan pembatalan sewa menutup pembayaran yang masih tertunda.
def test_cancel_closes_pending_payment(app):
    user, vehicle, location, _ = rental_data()
    rental = make_rental(user, vehicle, location, promo=None)
    payment = create_payment(
        rental, "Tunai", None, rental.total_payment, proof_file=None
    )

    cancel_rental(rental, user)
    db.session.commit()

    assert payment.verification_status == "Dibatalkan"
    assert Payment.query.filter_by(verification_status="Menunggu").count() == 0


# Memastikan pembayaran ditolak setelah tenggat reservasi terlewati.
def test_expired_booking_rejects_payment(app):
    user, vehicle, location, _ = rental_data()
    rental = make_rental(user, vehicle, location, promo=None)
    rental.payment_due_at = utc_now() - timedelta(seconds=1)
    db.session.commit()

    with pytest.raises(ValueError, match="Tenggat pembayaran"):
        create_payment(rental, "Tunai", None, rental.total_payment, None)


# Memastikan panjang kode pesanan sesuai batas kolom database.
def test_booking_code_fits_database_column(app):
    user, vehicle, location, _ = rental_data()
    rental = make_rental(user, vehicle, location, promo=None)
    assert len(rental.booking_code) <= 30
    assert Rental.query.count() == 1
