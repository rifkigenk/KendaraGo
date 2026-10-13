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


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def payment_deadline_for(rental):
    """Mengembalikan deadline eksplisit atau deadline kompatibilitas data lama."""
    if rental.payment_due_at:
        return rental.payment_due_at
    return rental.created_at + timedelta(
        hours=current_app.config["PAYMENT_DEADLINE_HOURS"]
    )


def calculate_price(
    vehicle,
    start_date,
    end_date,
    driver=None,
    promo_code=None,
    *,
    lock_promotion=False,
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
):
    """Memvalidasi permintaan lalu menyimpan pesanan dalam satu transaksi."""
    if start_date < date.today():
        raise ValueError("Tanggal mulai tidak boleh sudah lewat.")
    if start_date == date.today() and pickup_time <= datetime.now().time():
        raise ValueError("Waktu pengambilan hari ini harus berada di masa depan.")
    if not customer.profile or customer.profile.verification_status != "Terverifikasi":
        raise ValueError("Dokumen pelanggan harus terverifikasi sebelum memesan.")

    # Kunci baris armada sebelum mengecek jadwal. Request kedua untuk unit yang
    # sama akan menunggu transaksi pertama selesai lalu melihat reservasi terbaru.
    vehicle = db.session.execute(
        db.select(Vehicle).where(Vehicle.id == vehicle.id).with_for_update()
    ).scalar_one_or_none()
    if vehicle is None:
        raise ValueError("Kendaraan tidak ditemukan.")
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

    location_ids = {pickup_location_id, return_location_id}
    active_locations = db.session.scalars(
        db.select(Location.id).where(
            Location.id.in_(location_ids), Location.is_active.is_(True)
        )
    ).all()
    if set(active_locations) != location_ids:
        raise ValueError("Lokasi pengambilan atau pengembalian tidak valid.")

    # Harga disimpan pada pesanan (snapshot), sehingga perubahan harga kendaraan
    # di masa depan tidak mengubah tagihan pesanan yang sudah dibuat.
    prices = calculate_price(
        vehicle,
        start_date,
        end_date,
        driver,
        promo_code,
        lock_promotion=True,
    )
    promotion = prices.pop("promotion")
    rental = Rental(
        booking_code=f"KG-{date.today():%Y%m%d}-{token_hex(8).upper()}",
        customer_id=customer.id,
        vehicle_id=vehicle.id,
        driver_id=driver.id if driver else None,
        promotion_id=promotion.id if promotion else None,
        pickup_location_id=pickup_location_id,
        return_location_id=return_location_id,
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
            changed_by_id=customer.id,
            notes="Pemesanan dibuat",
        )
    )
    if promotion:
        db.session.add(
            PromotionUsage(
                promotion_id=promotion.id,
                rental_id=rental.id,
                customer_id=customer.id,
                discount_amount=rental.discount,
            )
        )
    notify(
        customer.id,
        "Pemesanan berhasil",
        f"Pesanan {rental.booking_code} berhasil dibuat.",
        f"/pelanggan/pesanan/{rental.id}",
    )
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ValueError(
            "Pemesanan berbenturan dengan transaksi lain. Silakan coba kembali."
        ) from error
    return rental


def change_status(rental, new_status, user, notes=None):
    """Mengubah status sekaligus membuat audit log dan notifikasi pelanggan."""
    old_status = rental.status
    rental.status = new_status
    db.session.add(
        RentalStatusLog(
            rental_id=rental.id,
            old_status=old_status,
            new_status=new_status,
            changed_by_id=user.id if user else None,
            notes=notes,
        )
    )
    notify(
        rental.customer_id,
        "Status pesanan diperbarui",
        f"{rental.booking_code}: {new_status}",
        f"/pelanggan/pesanan/{rental.id}",
    )


def cancel_rental(rental, user=None, *, automatic=False):
    """Membatalkan reservasi, membebaskan promo, dan menutup pembayaran tertunda."""
    allowed = {"Menunggu pembayaran", "Menunggu verifikasi pembayaran"}
    if rental.status not in allowed:
        raise ValueError("Pesanan tidak dapat dibatalkan pada status saat ini.")
    for payment in rental.payments:
        if payment.verification_status == "Menunggu":
            payment.verification_status = "Dibatalkan"
            payment.admin_notes = "Pesanan dibatalkan sebelum pembayaran diverifikasi."
    PromotionUsage.query.filter_by(rental_id=rental.id).delete()
    new_status = "Dibatalkan otomatis" if automatic else "Dibatalkan pelanggan"
    notes = "Tenggat pembayaran berakhir" if automatic else "Dibatalkan pelanggan"
    change_status(rental, new_status, user, notes)


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
