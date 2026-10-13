"""Route petugas untuk proses serah-terima dan pemeriksaan kendaraan."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db, limiter
from models import Fine, Rental, VehiclePickup, VehicleReturn
from services.rental_service import change_status
from utils.decorators import roles_required
from utils.file_handler import IMAGE_EXTENSIONS, delete_upload, save_upload
from utils.validators import bounded_int, decimal_amount, limited_text


bp = Blueprint("staff", __name__, url_prefix="/petugas")


@bp.before_request
@login_required
@roles_required("petugas", "admin")
def guard():
    """Membatasi halaman operasional untuk petugas dan admin."""
    pass


@bp.route("/")
def dashboard():
    today = datetime.today().date()
    pickups = Rental.query.filter(
        Rental.start_date == today, Rental.status.in_(["Dikonfirmasi", "Siap diambil"])
    ).all()
    returns = Rental.query.filter(
        Rental.end_date == today, Rental.status == "Sedang disewa"
    ).all()
    active = Rental.query.filter_by(status="Sedang disewa").all()
    overdue = [r for r in active if r.end_date < today]
    return render_template(
        "staff/dashboard.html",
        pickups=pickups,
        returns=returns,
        active=active,
        overdue=overdue,
    )


@bp.route("/pengambilan/<int:rental_id>", methods=["GET", "POST"])
@limiter.limit("30 per hour", methods=["POST"])
def pickup(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    if rental.status not in {"Dikonfirmasi", "Siap diambil"}:
        abort(400)
    if request.method == "POST":
        photo = None
        try:
            if not request.form.get("customer_approved"):
                raise ValueError("Persetujuan pelanggan wajib dicatat.")
            photo = save_upload(
                request.files.get("photo"), "inspections", IMAGE_EXTENSIONS, True
            )
            pickup = VehiclePickup(
                rental_id=rental.id,
                staff_id=current_user.id,
                pickup_at=datetime.now(),
                start_mileage=bounded_int(
                    request.form["start_mileage"], "Kilometer awal"
                ),
                fuel_condition=request.form.get("fuel_condition"),
                body_condition=limited_text(
                    request.form.get("body_condition"),
                    "Kondisi bodi",
                    maximum=1000,
                    required=True,
                ),
                tire_condition=limited_text(
                    request.form.get("tire_condition"),
                    "Kondisi ban",
                    maximum=100,
                    required=True,
                ),
                light_condition=limited_text(
                    request.form.get("light_condition"),
                    "Kondisi lampu",
                    maximum=100,
                    required=True,
                ),
                cleanliness=limited_text(
                    request.form.get("cleanliness"),
                    "Kebersihan",
                    maximum=100,
                    required=True,
                ),
                equipment=limited_text(
                    request.form.get("equipment"),
                    "Kelengkapan",
                    maximum=1000,
                    required=True,
                ),
                notes=limited_text(request.form.get("notes"), "Catatan", maximum=1000),
                customer_approved=bool(request.form.get("customer_approved")),
                photo=photo,
            )
            db.session.add(pickup)
            change_status(rental, "Sedang disewa", current_user, "Kendaraan diserahkan")
            rental.vehicle.status = "Sedang disewa"
            rental.vehicle.last_mileage = pickup.start_mileage
            if rental.driver:
                rental.driver.availability_status = "Bertugas"
            db.session.commit()
            flash("Pengambilan kendaraan berhasil diproses.", "success")
            return redirect(url_for("staff.dashboard"))
        except (ValueError, KeyError) as error:
            db.session.rollback()
            delete_upload(photo)
            flash(str(error), "danger")
    return render_template("staff/inspection.html", rental=rental, mode="pickup")


@bp.route("/pengembalian/<int:rental_id>", methods=["GET", "POST"])
@limiter.limit("30 per hour", methods=["POST"])
def vehicle_return(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    if rental.status not in {"Sedang disewa", "Menunggu pemeriksaan pengembalian"}:
        abort(400)
    if request.method == "POST":
        photo = None
        try:
            returned_at = datetime.now()
            late_days = max(0, (returned_at.date() - rental.end_date).days)
            late_fee = Decimal(rental.vehicle.category.late_fee_per_day) * late_days
            damage_fee = decimal_amount(
                request.form.get("damage_fee"), "Biaya kerusakan"
            )
            fuel_fee = decimal_amount(request.form.get("fuel_fee"), "Biaya bahan bakar")
            additional_fee = decimal_amount(
                request.form.get("additional_fee"), "Biaya tambahan"
            )
            end_mileage = bounded_int(request.form["end_mileage"], "Kilometer akhir")
            if rental.pickup and end_mileage < rental.pickup.start_mileage:
                raise ValueError(
                    "Kilometer akhir tidak boleh kurang dari kilometer awal."
                )
            photo = save_upload(
                request.files.get("photo"), "inspections", IMAGE_EXTENSIONS, True
            )
            item = VehicleReturn(
                rental_id=rental.id,
                staff_id=current_user.id,
                returned_at=returned_at,
                end_mileage=end_mileage,
                fuel_condition=request.form.get("fuel_condition"),
                vehicle_condition=limited_text(
                    request.form.get("vehicle_condition"),
                    "Kondisi kendaraan",
                    maximum=1500,
                    required=True,
                ),
                equipment=limited_text(
                    request.form.get("equipment"), "Kelengkapan", maximum=1000
                ),
                late_days=late_days,
                damage_notes=limited_text(
                    request.form.get("damage_notes"),
                    "Keterangan kerusakan",
                    maximum=1500,
                ),
                late_fee=late_fee,
                damage_fee=damage_fee,
                fuel_fee=fuel_fee,
                additional_fee=additional_fee,
                notes=limited_text(request.form.get("notes"), "Catatan", maximum=1000),
                needs_maintenance=bool(request.form.get("needs_maintenance")),
                photo=photo,
            )
            db.session.add(item)
            fine_parts = [
                ("Keterlambatan", late_fee),
                ("Kerusakan", damage_fee),
                ("Bahan bakar", fuel_fee),
                ("Tambahan", additional_fee),
            ]
            for fine_type, amount in fine_parts:
                if amount > 0:
                    db.session.add(
                        Fine(
                            rental_id=rental.id,
                            fine_type=fine_type,
                            amount=amount,
                            description=request.form.get("damage_notes"),
                        )
                    )
            change_status(
                rental, "Selesai", current_user, "Kendaraan dikembalikan dan diperiksa"
            )
            rental.vehicle.status = (
                "Perawatan" if item.needs_maintenance else "Tersedia"
            )
            rental.vehicle.last_mileage = item.end_mileage
            if rental.driver:
                rental.driver.availability_status = "Tersedia"
            db.session.commit()
            flash("Pengembalian berhasil diproses.", "success")
            return redirect(url_for("staff.dashboard"))
        except (ValueError, InvalidOperation, KeyError) as error:
            db.session.rollback()
            delete_upload(photo)
            flash(str(error), "danger")
    return render_template("staff/inspection.html", rental=rental, mode="return")
