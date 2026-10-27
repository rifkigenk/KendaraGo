"""Logika bisnis inti untuk menghitung harga dan mengelola penyewaan."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from secrets import token_hex

from flask import current_app
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (
    Driver,
    Location,
    Promotion,
    PromotionUsage,
    Rental,
    RentalStatusLog,
    Vehicle,
)
from services.availability_service import driver_is_available, vehicle_is_available
from services.notification_service import notify
from services.whatsapp_service import queue_rental_update


# ==========================================================
# 01. WAKTU DAN TENGGAT PEMBAYARAN
# Menggunakan waktu UTC dan menentukan batas pembayaran tiap pesanan.
# ==========================================================
# Menghasilkan waktu UTC tanpa zona untuk perbandingan timestamp database.
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def payment_deadline_for(rental):
    """Mengembalikan deadline eksplisit atau deadline kompatibilitas data lama."""
    if rental.payment_due_at:
        return rental.payment_due_at
    return rental.created_at + timedelta(
        hours=current_app.config["PAYMENT_DEADLINE_HOURS"]
    )


# ==========================================================
# 02. PERHITUNGAN BIAYA SEWA
# Menghitung durasi, biaya kendaraan, pengemudi, promo, dan deposit.
# ==========================================================
def calculate_price(
    vehicle,
    start_date,
    end_date,
    driver=None,
    promo_code=None,
    *,
    lock_promotion=False,
    loyal_customer=False,
):
    """Menghitung snapshot biaya kendaraan, sopir, diskon, dan deposit."""
    # Tanggal awal dan akhir sama-sama dihitung sebagai hari sewa.
    days = (end_date - start_date).days + 1
    if days < 1:
        raise ValueError("Tanggal selesai harus sama atau setelah tanggal mulai.")
    vehicle_subtotal = Decimal(vehicle.daily_price) * days
    driver_fee = Decimal(driver.daily_rate) * days if driver else Decimal("0")
    subtotal = vehicle_subtotal + driver_fee
    discount = Decimal("0")
    promotion = None
    # Promo hanya dipakai bila aktif, belum kedaluwarsa, memenuhi minimum,
    # dan kuotanya masih tersedia.
    if promo_code:
        promotion_query = Promotion.query.filter_by(
            code=promo_code.upper(), is_active=True
        )
        if lock_promotion:
            promotion_query = promotion_query.with_for_update()
        promotion = promotion_query.first()
        today = date.today()
        if not promotion or not (promotion.start_date <= today <= promotion.end_date):
            raise ValueError("Kode promo tidak valid atau sudah kedaluwarsa.")
        if subtotal < Decimal(promotion.minimum_transaction or 0):
            raise ValueError("Nilai transaksi belum memenuhi minimum promo.")
        if (
            promotion.quota is not None
            and PromotionUsage.query.filter_by(promotion_id=promotion.id).count()
            >= promotion.quota
        ):
            raise ValueError("Kuota promo sudah habis.")
        if promotion.discount_type == "Persentase":
            discount = subtotal * Decimal(promotion.discount_value) / Decimal("100")
            if promotion.max_discount:
                discount = min(discount, Decimal(promotion.max_discount))
        else:
            discount = Decimal(promotion.discount_value)
        discount = min(discount, subtotal)
    elif loyal_customer and subtotal >= Decimal("300000"):
        discount = min(subtotal * Decimal("0.10"), Decimal("150000"))
    total = subtotal - discount + Decimal(vehicle.deposit)
    return {
        "duration_days": days,
        "daily_price": vehicle.daily_price,
        "vehicle_subtotal": vehicle_subtotal,
        "driver_fee": driver_fee,
        "additional_fee": Decimal("0"),
        "discount": discount,
        "deposit": vehicle.deposit,
        "total_payment": total,
        "promotion": promotion,
    }


# ==========================================================
# 03. PEMBUATAN DATA PENYEWAAN
# Memvalidasi pilihan dan jadwal lalu menyimpan pesanan beserta harga.
# ==========================================================
def create_rental(
    customer,
    vehicle,
    start_date,
    end_date,
    pickup_time,
    pickup_location_id,
    return_location_id,
    driver=None,
    promo_code=None,
    notes=None,
    *,
    pickup_address=None,
    return_address=None,
    request_key=None,
    request_hash=None,
    pending_approval=False,
    guest=None,
    identity=None,
):
    """Memvalidasi permintaan lalu menyimpan pesanan dalam satu transaksi."""
    if identity is not None:
        from services.identity_service import validate_identity

        identity = validate_identity(
            identity.get("type"), identity.get("number"), identity.get("country", "")
        )
    if start_date < date.today():
        raise ValueError("Tanggal mulai tidak boleh sudah lewat.")
    if start_date == date.today() and pickup_time <= datetime.now().time():
        raise ValueError("Waktu pengambilan hari ini harus berada di masa depan.")
    if not pending_approval and (
        not customer
        or not customer.profile
        or customer.profile.verification_status != "Terverifikasi"
    ):
        raise ValueError("Dokumen pelanggan harus terverifikasi sebelum memesan.")

    # Kunci baris armada sebelum mengecek jadwal. Request kedua untuk unit yang
    # sama akan menunggu transaksi pertama selesai lalu melihat reservasi terbaru.
    vehicle = db.session.execute(
        db.select(Vehicle).where(Vehicle.id == vehicle.id).with_for_update()
    ).scalar_one_or_none()
    if vehicle is None:
        raise ValueError("Kendaraan tidak ditemukan.")
    if request_key:
        previous = (
            Rental.query.filter_by(
                customer_id=customer.id if customer else None,
                request_key=request_key,
                **({"guest_session_key": guest["session_key"]} if not customer else {}),
            )
            .with_for_update()
            .first()
        )
        if previous:
            if previous.request_hash != request_hash:
                raise ValueError("Kunci pemesanan sudah digunakan untuk data berbeda.")
            return previous
    if not vehicle.is_active or vehicle.status in {"Perawatan", "Tidak aktif"}:
        raise ValueError("Kendaraan sedang tidak dapat disewa.")
    if not vehicle_is_available(vehicle.id, start_date, end_date, lock=True):
        raise ValueError("Kendaraan tidak tersedia pada periode tersebut.")

    if driver:
        driver = db.session.execute(
            db.select(Driver).where(Driver.id == driver.id).with_for_update()
        ).scalar_one_or_none()
        if not driver or not driver.is_active:
            raise ValueError("Pengemudi tidak tersedia.")
        if not driver_is_available(driver.id, start_date, end_date, lock=True):
            raise ValueError("Pengemudi tidak tersedia pada periode tersebut.")

    from services.location_service import validate_address

    def snapshot(address, location_id):
        if address is None:
            office = db.session.get(Location, location_id) if location_id else None
            address = {
                "kind": "office",
                "office_id": location_id,
                "confirmed": True,
                "office_updated_at": office.updated_at.isoformat() if office else "",
            }
        return validate_address(address)

    pickup_address = snapshot(pickup_address, pickup_location_id)
    return_address = snapshot(return_address, return_location_id)

    # Harga disimpan pada pesanan (snapshot), sehingga perubahan harga kendaraan
    # di masa depan tidak mengubah tagihan pesanan yang sudah dibuat.
    prices = calculate_price(
        vehicle,
        start_date,
        end_date,
        driver,
        promo_code,
        lock_promotion=True,
        loyal_customer=bool(customer)
        and Rental.query.filter_by(customer_id=customer.id, status="Selesai").count()
        > 0,
    )
    promotion = prices.pop("promotion")
    rental = Rental(
        booking_code=f"KG-{date.today():%Y%m%d}-{token_hex(8).upper()}",
        customer_id=customer.id if customer else None,
        guest_name=guest["name"] if guest else None,
        guest_phone=guest["phone"] if guest else None,
        guest_session_key=guest["session_key"] if guest else None,
        identity_type=identity["type"] if identity else None,
        identity_number=identity["number"] if identity else None,
        identity_country=identity["country"] if identity else None,
        status="Menunggu persetujuan" if pending_approval else "Menunggu pembayaran",
        vehicle_id=vehicle.id,
        driver_id=driver.id if driver else None,
        promotion_id=promotion.id if promotion else None,
        pickup_location_id=pickup_address.get("office_id"),
        return_location_id=return_address.get("office_id"),
        pickup_address=pickup_address,
        return_address=return_address,
        request_key=request_key,
        request_hash=request_hash,
        start_date=start_date,
        end_date=end_date,
        pickup_time=pickup_time,
        payment_due_at=utc_now()
        + timedelta(hours=current_app.config["PAYMENT_DEADLINE_HOURS"]),
        with_driver=driver is not None,
        customer_notes=notes,
        **prices,
    )
    db.session.add(rental)
    db.session.flush()
    db.session.add(
        RentalStatusLog(
            rental_id=rental.id,
            new_status=rental.status,
            changed_by_id=customer.id if customer else None,
            notes="Pemesanan dibuat",
        )
    )
    if promotion and customer:
        db.session.add(
            PromotionUsage(
                promotion_id=promotion.id,
                rental_id=rental.id,
                customer_id=customer.id,
                discount_amount=rental.discount,
            )
        )
    if customer:
        notify(
            customer.id,
            "Pemesanan berhasil",
            f"Pesanan {rental.booking_code} berhasil dibuat.",
            f"/pelanggan/pesanan/{rental.id}",
        )
    queue_rental_update(rental)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ValueError(
            "Pemesanan berbenturan dengan transaksi lain. Silakan coba kembali."
        ) from error
    return rental


# ==========================================================
# 04. PERUBAHAN STATUS DAN RIWAYAT
# Mencatat status baru, pelaku perubahan, catatan, dan notifikasi.
# ==========================================================
def change_status(rental, new_status, user, notes=None):
    """Mengubah status sekaligus membuat audit log dan notifikasi pelanggan."""
    queue_rental_notification = rental.status != new_status
    old_status = rental.status
    rental.status = new_status
    if queue_rental_notification:
        queue_rental_update(rental)
    db.session.add(
        RentalStatusLog(
            rental_id=rental.id,
            old_status=old_status,
            new_status=new_status,
            changed_by_id=user.id if user else None,
            notes=notes,
        )
    )
    if rental.customer_id:
        notify(
            rental.customer_id,
            "Status pesanan diperbarui",
            f"{rental.booking_code}: {new_status}",
            f"/pelanggan/pesanan/{rental.id}",
        )


# ==========================================================
# 05. PEMBATALAN PESANAN
# Menolak pembatalan yang tidak valid dan melepas penggunaan promo.
# ==========================================================
def cancel_rental(rental, user=None, *, automatic=False):
    """Membatalkan reservasi, membebaskan promo, dan menutup pembayaran tertunda."""
    allowed = {
        "Menunggu persetujuan",
        "Menunggu pembayaran",
        "Menunggu verifikasi pembayaran",
    }
    if rental.status not in allowed:
        raise ValueError("Pesanan tidak dapat dibatalkan pada status saat ini.")
    for payment in rental.payments:
        if payment.verification_status == "Menunggu":
            payment.verification_status = "Dibatalkan"
            payment.admin_notes = "Pesanan dibatalkan sebelum pembayaran diverifikasi."
    PromotionUsage.query.filter_by(rental_id=rental.id).delete()
    admin_cancel = user is not None and user.role == "admin"
    new_status = (
        "Dibatalkan otomatis"
        if automatic
        else ("Dibatalkan admin" if admin_cancel else "Dibatalkan pelanggan")
    )
    notes = "Tenggat pembayaran berakhir" if automatic else new_status
    change_status(rental, new_status, user, notes)


# ==========================================================
# 06. PEMBATALAN OTOMATIS
# Menutup pesanan menunggu pembayaran yang sudah melewati tenggat.
# ==========================================================
def expire_unpaid_rentals(*, commit=True):
    """Menutup pesanan yang melewati tenggat, termasuk data lama tanpa deadline."""
    now = utc_now()
    legacy_cutoff = now - timedelta(hours=current_app.config["PAYMENT_DEADLINE_HOURS"])
    expired = Rental.query.filter(
        Rental.status == "Menunggu pembayaran",
        or_(
            Rental.payment_due_at <= now,
            and_(
                Rental.payment_due_at.is_(None),
                Rental.created_at <= legacy_cutoff,
            ),
        ),
    ).all()
    for rental in expired:
        cancel_rental(rental, automatic=True)
    if expired and commit:
        db.session.commit()
    return len(expired)
