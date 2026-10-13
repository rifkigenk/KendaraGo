"""Logika untuk mendeteksi bentrok jadwal kendaraan dan pengemudi."""

from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import and_, or_

from models import Maintenance, Rental


BLOCKING_STATUSES = [
    "Menunggu pembayaran",
    "Menunggu verifikasi pembayaran",
    "Dikonfirmasi",
    "Siap diambil",
    "Sedang disewa",
    "Menunggu pemeriksaan pengembalian",
]
MAINTENANCE_STATUSES = ["Dijadwalkan", "Sedang dikerjakan"]


def blocking_rental_condition():
    """Status menunggu hanya memblokir selama tenggat pembayarannya berlaku."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    legacy_cutoff = now - timedelta(hours=current_app.config["PAYMENT_DEADLINE_HOURS"])
    long_lived_statuses = [
        status for status in BLOCKING_STATUSES if status != "Menunggu pembayaran"
    ]
    return or_(
        Rental.status.in_(long_lived_statuses),
        and_(
            Rental.status == "Menunggu pembayaran",
            or_(
                Rental.payment_due_at > now,
                and_(
                    Rental.payment_due_at.is_(None),
                    Rental.created_at > legacy_cutoff,
                ),
            ),
        ),
    )


def vehicle_is_available(
    vehicle_id, start_date, end_date, exclude_rental_id=None, *, lock=False
):
    """Bernilai True jika tidak ada sewa atau perawatan pada rentang tanggal."""
    rental_query = Rental.query.filter(
        Rental.vehicle_id == vehicle_id,
        blocking_rental_condition(),
        Rental.start_date <= end_date,
        Rental.end_date >= start_date,
    )
    if exclude_rental_id:
        rental_query = rental_query.filter(Rental.id != exclude_rental_id)
    if lock:
        rental_query = rental_query.with_for_update()
    if rental_query.first():
        return False
    maintenance_query = Maintenance.query.filter(
        Maintenance.vehicle_id == vehicle_id,
        Maintenance.status.in_(MAINTENANCE_STATUSES),
        Maintenance.start_date <= end_date,
        Maintenance.estimated_end_date >= start_date,
    )
    if lock:
        maintenance_query = maintenance_query.with_for_update()
    return maintenance_query.first() is None


def driver_is_available(
    driver_id, start_date, end_date, exclude_rental_id=None, *, lock=False
):
    """Bernilai True jika pengemudi belum dipakai oleh pesanan lain."""
    query = Rental.query.filter(
        Rental.driver_id == driver_id,
        blocking_rental_condition(),
        Rental.start_date <= end_date,
        Rental.end_date >= start_date,
    )
    if exclude_rental_id:
        query = query.filter(Rental.id != exclude_rental_id)
    if lock:
        query = query.with_for_update()
    return not query.first()
