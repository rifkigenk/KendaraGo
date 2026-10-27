"""Short polling across WSGI workers, always reading committed database state."""

import hashlib
import json
from datetime import date, timedelta

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user
from sqlalchemy.orm import selectinload

from extensions import db
from models import Rental, Vehicle, Driver, PromotionUsage
from models.entities import now
from services.location_service import validate_address
from services.rental_service import cancel_rental, change_status, utc_now
from services.availability_service import vehicle_is_available, driver_is_available
from flask import current_app
from routes.booking_form import guest_session_key
from utils.decorators import roles_required

bp = Blueprint("booking_sync", __name__, url_prefix="/api/pesanan")
TRANSITIONS = {
    "Menunggu persetujuan": ["Menunggu pembayaran", "Ditolak"],
    "Menunggu pembayaran": ["Dibatalkan admin"],
    "Menunggu verifikasi pembayaran": ["Dibatalkan admin"],
    "Dikonfirmasi": ["Siap diambil"],
    "Siap diambil": ["Dikonfirmasi"],
}
EDITABLE = {
    "Menunggu persetujuan",
    "Menunggu pembayaran",
    "Menunggu verifikasi pembayaran",
    "Dikonfirmasi",
}


@bp.before_request
def guard():
    if not current_user.is_authenticated:
        if not guest_session_key():
            abort(401)
    elif not current_user.is_active:
        abort(403)


def scoped_query():
    query = Rental.query
    if not current_user.is_authenticated:
        query = query.filter_by(customer_id=None, guest_session_key=guest_session_key())
    elif current_user.role not in {"admin", "petugas"}:
        query = query.filter_by(customer_id=current_user.id)
    return query


def serialize(r):
    return dict(
        id=r.id,
        booking_code=r.booking_code,
        status=r.status,
        customer_id=r.customer_id,
        customer_name=r.customer_name,
        vehicle_id=r.vehicle_id,
        vehicle_name=r.vehicle.name,
        start_date=r.start_date.isoformat(),
        end_date=r.end_date.isoformat(),
        pickup_time=r.pickup_time.isoformat(),
        pickup_address=r.pickup_address,
        return_address=r.return_address,
        notes=r.customer_notes,
        updated_at=r.updated_at.isoformat(),
        total=str(r.total_payment),
    )


@bp.get("")
def feed():
    rentals = (
        scoped_query()
        .options(selectinload(Rental.customer), selectinload(Rental.vehicle))
        .order_by(Rental.id.desc())
        .all()
    )
    rows = [serialize(r) for r in rentals]
    revision = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    return jsonify(
        revision=revision,
        rentals=rows,
        html=render_template("components/booking_list.html", rentals=rentals),
    )


@bp.get("/<int:rental_id>")
def detail(rental_id):
    rental = scoped_query().filter_by(id=rental_id).first_or_404()
    return jsonify(
        **serialize(rental),
        html=render_template("components/booking_locations.html", rental=rental),
        transitions=allowed_transitions(rental),
    )


@bp.post("/<int:rental_id>/lokasi")
def update_locations(rental_id):
    rental = scoped_query().filter_by(id=rental_id).with_for_update().first_or_404()
    data = request.get_json(silent=True) or {}
    if data.get("version") != rental.updated_at.isoformat():
        return (
            jsonify(error="Pesanan berubah. Muat ulang detail dan konfirmasi kembali."),
            409,
        )
    if rental.status not in EDITABLE:
        return jsonify(error="Lokasi tidak dapat diubah pada status ini."), 409
    try:
        pickup = validate_address(data.get("pickup_address"))
        dropoff = (
            pickup.copy()
            if data.get("same_location") is True
            else validate_address(data.get("return_address"))
        )
        rental.pickup_address, rental.return_address = pickup, dropoff
        rental.pickup_location_id, rental.return_location_id = pickup.get(
            "office_id"
        ), dropoff.get("office_id")
        notes = data.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 1000:
            raise ValueError("Catatan maksimal 1000 karakter.")
        rental.customer_notes = notes.strip()
        rental.updated_at = now()
        db.session.commit()
        return jsonify(
            message="Lokasi berhasil disimpan.", version=rental.updated_at.isoformat()
        )
    except ValueError as error:
        db.session.rollback()
        return jsonify(error=str(error)), 422


@bp.post("/<int:rental_id>/status")
@roles_required("admin", "petugas")
def status(rental_id):
    rental = Rental.query.filter_by(id=rental_id).first_or_404()
    # Serialize approvals on the vehicle before inspecting overlapping reservations.
    db.session.execute(
        db.select(Vehicle).where(Vehicle.id == rental.vehicle_id).with_for_update()
    ).scalar_one()
    rental = (
        Rental.query.filter_by(id=rental_id)
        .populate_existing()
        .with_for_update()
        .first_or_404()
    )
    data = request.get_json(silent=True) or {}
    # Retrying an already applied transition is harmless.
    if data.get("status") == rental.status:
        return jsonify(message="Status sudah tersimpan.")
    if data.get("version") != rental.updated_at.isoformat():
        return jsonify(error="Status berubah. Muat ulang sebelum mencoba kembali."), 409
    target = data.get("status")
    if target not in allowed_transitions(rental):
        return (
            jsonify(
                error="Perubahan status tidak diizinkan. Gunakan verifikasi pembayaran atau pemeriksaan petugas."
            ),
            422,
        )
    if rental.status == "Menunggu persetujuan":
        if target == "Menunggu pembayaran":
            if (
                rental.start_date < date.today()
                or not rental.vehicle.is_active
                or rental.vehicle.status in {"Perawatan", "Tidak aktif"}
            ):
                return (
                    jsonify(error="Jadwal sudah lewat atau kendaraan tidak aktif."),
                    409,
                )
            if not vehicle_is_available(
                rental.vehicle_id,
                rental.start_date,
                rental.end_date,
                rental.id,
                lock=True,
            ):
                return (
                    jsonify(
                        error="Kendaraan sudah dipesan pada periode ini. Pesanan belum disetujui."
                    ),
                    409,
                )
            if rental.driver_id:
                driver = db.session.execute(
                    db.select(Driver)
                    .where(Driver.id == rental.driver_id)
                    .with_for_update()
                ).scalar_one()
                if not driver.is_active or not driver_is_available(
                    driver.id, rental.start_date, rental.end_date, rental.id, lock=True
                ):
                    return (
                        jsonify(error="Pengemudi tidak tersedia pada periode ini."),
                        409,
                    )
            rental.payment_due_at = utc_now() + timedelta(
                hours=current_app.config["PAYMENT_DEADLINE_HOURS"]
            )
        else:
            PromotionUsage.query.filter_by(rental_id=rental.id).delete()
        change_status(
            rental,
            target,
            current_user,
            (
                "Pesanan disetujui"
                if target == "Menunggu pembayaran"
                else "Pesanan ditolak"
            ),
        )
    elif target == "Dibatalkan admin":
        cancel_rental(rental, current_user)
    else:
        change_status(
            rental, target, current_user, "Diperbarui melalui dashboard admin"
        )
    rental.updated_at = now()
    db.session.commit()
    return jsonify(message="Status berhasil disimpan.")


@bp.get("/<int:rental_id>/admin")
@roles_required("admin", "petugas")
def admin_detail(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    return render_template(
        "admin/rental_detail.html",
        rental=rental,
        transitions=allowed_transitions(rental),
    )


def allowed_transitions(rental):
    if not current_user.is_authenticated or current_user.role not in {
        "admin",
        "petugas",
    }:
        return []
    if current_user.role == "petugas" and rental.status != "Menunggu persetujuan":
        return []
    return TRANSITIONS.get(rental.status, [])
