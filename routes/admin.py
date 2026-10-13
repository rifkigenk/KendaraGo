"""Route admin untuk armada, verifikasi, pembayaran, dan laporan."""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO, TextIOWrapper

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, fresh_login_required, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from extensions import db, limiter
from models import (
    Category,
    CustomerProfile,
    Driver,
    Location,
    Payment,
    Rental,
    User,
    Vehicle,
    VehicleSpecification,
)
from services.availability_service import driver_is_available, vehicle_is_available
from services.payment_service import verify_payment
from services.report_service import rentals_excel
from utils.decorators import roles_required
from utils.file_handler import IMAGE_EXTENSIONS, delete_upload, save_upload
from utils.validators import bounded_int, decimal_amount, limited_text, safe_http_url


# Blueprint admin dipisah agar kontrol akses dan URL mudah dikenali.
bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@login_required
@roles_required("admin")
def guard():
    """Menjalankan pemeriksaan role admin sebelum setiap request Blueprint."""
    pass


@bp.route("/")
def dashboard():
    first_day = date.today().replace(day=1)
    stats = {
        "vehicles": Vehicle.query.count(),
        "available": Vehicle.query.filter_by(status="Tersedia", is_active=True).count(),
        "rented": Vehicle.query.filter_by(status="Sedang disewa").count(),
        "maintenance": Vehicle.query.filter_by(status="Perawatan").count(),
        "customers": User.query.filter_by(role="pelanggan").count(),
        "pending_profiles": CustomerProfile.query.filter_by(
            verification_status="Menunggu verifikasi"
        ).count(),
        "monthly_rentals": Rental.query.filter(Rental.created_at >= first_day).count(),
        "pending_payments": Payment.query.filter_by(
            verification_status="Menunggu"
        ).count(),
    }
    revenue = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.verification_status == "Diverifikasi",
            Payment.payment_date >= first_day,
        )
        .scalar()
    )
    recent = Rental.query.order_by(Rental.created_at.desc()).limit(8).all()
    return render_template(
        "admin/dashboard.html", stats=stats, revenue=revenue, recent=recent
    )


@bp.route("/kendaraan")
def vehicles():
    page = Vehicle.query.order_by(Vehicle.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=50, error_out=False
    )
    return render_template("admin/vehicles.html", vehicles=page.items, page=page)


IMPORT_COLUMNS = [
    "code",
    "category",
    "vehicle_type",
    "name",
    "brand",
    "model",
    "license_plate",
    "production_year",
    "color",
    "passenger_capacity",
    "transmission",
    "fuel_type",
    "daily_price",
    "deposit",
    "location",
    "description",
    "image",
    "vehicle_class",
    "brand_origin",
    "engine_layout",
    "displacement_cc",
    "power_hp",
    "torque_nm",
    "gearbox",
    "final_drive",
    "fuel_capacity_l",
    "battery_capacity_kwh",
    "estimated_range_km",
    "seat_height_mm",
    "wet_weight_kg",
    "ground_clearance_mm",
    "front_wheel",
    "rear_wheel",
    "abs_type",
    "rider_aids",
    "luggage",
    "source_url",
]


def optional_number(row, key, number_type=Decimal):
    value = (row.get(key) or "").strip()
    return number_type(value) if value else None


@bp.route("/kendaraan/impor", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def import_vehicles():
    if request.method == "POST":
        upload = request.files.get("csv_file")
        if not upload or not upload.filename.lower().endswith(".csv"):
            flash("Pilih file CSV yang valid.", "danger")
            return render_template("admin/import_vehicles.html", columns=IMPORT_COLUMNS)
        try:
            reader = csv.DictReader(TextIOWrapper(upload.stream, encoding="utf-8-sig"))
            missing = {
                "code",
                "category",
                "vehicle_type",
                "name",
                "brand",
                "license_plate",
                "daily_price",
                "location",
            } - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Kolom wajib belum ada: {', '.join(sorted(missing))}")
            created = 0
            for line_number, row in enumerate(reader, start=2):
                if line_number > 1001:
                    raise ValueError("Impor dibatasi maksimal 1.000 baris per file.")
                code = row["code"].strip().upper()
                if not code:
                    raise ValueError(f"Baris {line_number}: kode kosong.")
                if Vehicle.query.filter_by(code=code).first():
                    continue
                category_name = row["category"].strip()
                category = Category.query.filter_by(name=category_name).first()
                if not category:
                    category = Category(
                        name=category_name,
                        vehicle_type=row["vehicle_type"].strip(),
                        late_fee_per_day=0,
                        description=f"Kategori impor {category_name}",
                    )
                    db.session.add(category)
                    db.session.flush()
                location = Location.query.filter_by(
                    name=row["location"].strip()
                ).first()
                if not location:
                    raise ValueError(
                        f"Baris {line_number}: lokasi '{row['location']}' belum terdaftar."
                    )
                vehicle = Vehicle(
                    code=code,
                    category=category,
                    location=location,
                    name=row["name"].strip(),
                    brand=row["brand"].strip(),
                    model=(row.get("model") or "").strip(),
                    license_plate=row["license_plate"].strip().upper(),
                    production_year=int(
                        row.get("production_year") or date.today().year
                    ),
                    color=(row.get("color") or "").strip(),
                    passenger_capacity=int(row.get("passenger_capacity") or 2),
                    transmission=(row.get("transmission") or "Manual").strip(),
                    fuel_type=(row.get("fuel_type") or "Bensin").strip(),
                    daily_price=Decimal(row["daily_price"]),
                    deposit=Decimal(row.get("deposit") or 0),
                    description=(row.get("description") or "").strip(),
                    main_image=(
                        row.get("image") or "vehicles/adventure-bike-green.png"
                    ).strip(),
                    status="Tersedia",
                    is_active=True,
                )
                db.session.add(vehicle)
                db.session.flush()
                if (row.get("vehicle_class") or "").strip():
                    db.session.add(
                        VehicleSpecification(
                            vehicle_id=vehicle.id,
                            vehicle_class=row["vehicle_class"].strip(),
                            brand_origin=(row.get("brand_origin") or "").strip(),
                            engine_layout=(row.get("engine_layout") or "").strip(),
                            displacement_cc=optional_number(
                                row, "displacement_cc", int
                            ),
                            power_hp=optional_number(row, "power_hp"),
                            torque_nm=optional_number(row, "torque_nm"),
                            gearbox=(row.get("gearbox") or "").strip(),
                            final_drive=(row.get("final_drive") or "").strip(),
                            fuel_capacity_l=optional_number(row, "fuel_capacity_l"),
                            battery_capacity_kwh=optional_number(
                                row, "battery_capacity_kwh"
                            ),
                            estimated_range_km=optional_number(
                                row, "estimated_range_km", int
                            ),
                            seat_height_mm=optional_number(row, "seat_height_mm", int),
                            wet_weight_kg=optional_number(row, "wet_weight_kg"),
                            ground_clearance_mm=optional_number(
                                row, "ground_clearance_mm", int
                            ),
                            front_wheel=(row.get("front_wheel") or "").strip(),
                            rear_wheel=(row.get("rear_wheel") or "").strip(),
                            abs_type=(row.get("abs_type") or "").strip(),
                            rider_aids=(row.get("rider_aids") or "").strip(),
                            luggage=(row.get("luggage") or "").strip(),
                            source_name=f"{row['brand'].strip()} official",
                            source_url=safe_http_url(
                                row.get("source_url"), "URL sumber"
                            ),
                            source_checked_at=datetime.now(),
                        )
                    )
                created += 1
            db.session.commit()
            flash(f"Impor selesai: {created} kendaraan baru ditambahkan.", "success")
            return redirect(url_for("admin.vehicles"))
        except (ValueError, InvalidOperation, UnicodeDecodeError) as error:
            db.session.rollback()
            flash(f"Impor dibatalkan: {error}", "danger")
    return render_template("admin/import_vehicles.html", columns=IMPORT_COLUMNS)


@bp.route("/kendaraan/template-impor.csv")
def vehicle_import_template():
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=IMPORT_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "code": "TOUR-999",
            "category": "Adventure Touring",
            "vehicle_type": "Sepeda motor",
            "name": "Contoh Global Tourer",
            "brand": "Contoh",
            "model": "GT 900",
            "license_plate": "B 9999 TGO",
            "production_year": date.today().year,
            "color": "Biru",
            "passenger_capacity": 2,
            "transmission": "6 percepatan",
            "fuel_type": "Bensin",
            "daily_price": 1000000,
            "deposit": 2000000,
            "location": "Jakarta Pusat",
            "description": "Motor touring contoh",
            "image": "vehicles/adventure-bike-green.png",
            "vehicle_class": "Adventure Touring",
            "brand_origin": "Jepang",
            "engine_layout": "Parallel-twin liquid-cooled",
            "displacement_cc": 900,
            "power_hp": 100,
            "torque_nm": 90,
            "gearbox": "6 percepatan",
            "final_drive": "Chain",
            "fuel_capacity_l": 20,
            "estimated_range_km": 400,
            "seat_height_mm": 840,
            "wet_weight_kg": 230,
            "ground_clearance_mm": 220,
            "front_wheel": "19 inci",
            "rear_wheel": "17 inci",
            "abs_type": "Cornering ABS",
            "rider_aids": "Traction control; cruise control; ride modes",
            "luggage": "Pannier dan top box",
            "source_url": "https://manufacturer.example/specifications",
        }
    )
    data = BytesIO(output.getvalue().encode("utf-8-sig"))
    return send_file(
        data,
        mimetype="text/csv",
        as_attachment=True,
        download_name="template-impor-kendaraan.csv",
    )


@bp.route("/kendaraan/tambah", methods=["GET", "POST"])
@bp.route("/kendaraan/<int:vehicle_id>/ubah", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
def vehicle_form(vehicle_id=None):
    vehicle = Vehicle.query.get_or_404(vehicle_id) if vehicle_id else Vehicle()
    new_image = None
    old_image = vehicle.main_image
    if request.method == "POST":
        try:
            category_id = bounded_int(
                request.form["category_id"], "Kategori", minimum=1
            )
            location_id = bounded_int(request.form["location_id"], "Lokasi", minimum=1)
            if not db.session.get(Category, category_id):
                raise ValueError("Kategori tidak valid.")
            if not db.session.get(Location, location_id):
                raise ValueError("Lokasi tidak valid.")
            transmission = request.form["transmission"]
            fuel_type = request.form["fuel_type"]
            status = request.form.get("status", "Tersedia")
            if transmission not in {"Manual", "Otomatis"}:
                raise ValueError("Transmisi tidak valid.")
            if fuel_type not in {"Bensin", "Diesel", "Listrik", "Hybrid"}:
                raise ValueError("Jenis bahan bakar tidak valid.")
            if status not in {"Tersedia", "Perawatan", "Tidak aktif"}:
                raise ValueError("Status kendaraan tidak valid.")

            vehicle.code = limited_text(
                request.form["code"], "Kode", maximum=30, required=True
            ).upper()
            vehicle.category_id = category_id
            vehicle.location_id = location_id
            vehicle.name = limited_text(
                request.form["name"], "Nama kendaraan", maximum=120, required=True
            )
            vehicle.brand = limited_text(
                request.form["brand"], "Merek", maximum=80, required=True
            )
            vehicle.model = limited_text(request.form.get("model"), "Model", maximum=80)
            vehicle.license_plate = limited_text(
                request.form["license_plate"],
                "Nomor polisi",
                maximum=20,
                required=True,
            ).upper()
            vehicle.production_year = bounded_int(
                request.form["production_year"],
                "Tahun produksi",
                minimum=1950,
                maximum=date.today().year + 1,
            )
            vehicle.color = limited_text(request.form.get("color"), "Warna", maximum=40)
            vehicle.passenger_capacity = bounded_int(
                request.form.get("passenger_capacity") or 2,
                "Kapasitas penumpang",
                minimum=1,
                maximum=100,
            )
            vehicle.transmission = transmission
            vehicle.fuel_type = fuel_type
            vehicle.daily_price = decimal_amount(
                request.form["daily_price"], "Harga harian", minimum=Decimal("1")
            )
            vehicle.deposit = decimal_amount(request.form.get("deposit"), "Deposit")
            vehicle.description = limited_text(
                request.form.get("description"), "Deskripsi", maximum=5000
            )
            vehicle.status = status
            vehicle.is_active = bool(request.form.get("is_active"))
            if request.files.get("main_image"):
                new_image = save_upload(
                    request.files["main_image"],
                    "vehicles/user",
                    IMAGE_EXTENSIONS,
                    True,
                    private=False,
                )
                vehicle.main_image = new_image
            db.session.add(vehicle)
            db.session.commit()
            if new_image and old_image and old_image.startswith("vehicles/user/"):
                delete_upload(old_image, private=False)
            flash("Data kendaraan berhasil disimpan.", "success")
            return redirect(url_for("admin.vehicles"))
        except (ValueError, InvalidOperation, KeyError) as error:
            db.session.rollback()
            delete_upload(new_image, private=False)
            flash(f"Data tidak valid: {error}", "danger")
        except IntegrityError:
            db.session.rollback()
            delete_upload(new_image, private=False)
            flash("Kode atau nomor polisi kendaraan sudah digunakan.", "danger")
    return render_template(
        "admin/vehicle_form.html",
        vehicle=vehicle,
        categories=Category.query.filter_by(is_active=True).all(),
        locations=Location.query.filter_by(is_active=True).all(),
    )


@bp.route("/kendaraan/<int:vehicle_id>/status", methods=["POST"])
@limiter.limit("30 per hour")
def toggle_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    vehicle.is_active = not vehicle.is_active
    if not vehicle.is_active:
        vehicle.status = "Tidak aktif"
    elif vehicle.status == "Tidak aktif":
        vehicle.status = "Tersedia"
    db.session.commit()
    flash("Status kendaraan diperbarui.", "success")
    return redirect(url_for("admin.vehicles"))


@bp.route("/pelanggan/verifikasi")
def verifications():
    profiles = CustomerProfile.query.order_by(CustomerProfile.updated_at.desc()).all()
    return render_template("admin/verifications.html", profiles=profiles)


@bp.route("/pelanggan/<int:profile_id>/verifikasi", methods=["POST"])
@limiter.limit("30 per hour")
def verify_profile(profile_id):
    profile = CustomerProfile.query.get_or_404(profile_id)
    action = request.form.get("action")
    if action not in {"accept", "reject"}:
        abort(400)
    try:
        rejection_reason = (
            limited_text(
                request.form.get("reason"),
                "Alasan penolakan",
                maximum=1000,
                required=True,
            )
            if action == "reject"
            else None
        )
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("admin.verifications"))
    profile.verification_status = "Terverifikasi" if action == "accept" else "Ditolak"
    profile.rejection_reason = rejection_reason
    from services.notification_service import notify

    notify(
        profile.user_id,
        "Verifikasi dokumen",
        f"Dokumen Anda {profile.verification_status.lower()}.",
        "/pelanggan/profil",
    )
    db.session.commit()
    flash("Status verifikasi diperbarui.", "success")
    return redirect(url_for("admin.verifications"))


@bp.route("/pembayaran")
def payments():
    return render_template(
        "admin/payments.html",
        payments=Payment.query.order_by(Payment.created_at.desc()).all(),
    )


@bp.route("/pembayaran/<int:payment_id>/verifikasi", methods=["POST"])
@fresh_login_required
@limiter.limit("30 per hour")
def payment_verification(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    action = request.form.get("action")
    if action not in {"accept", "reject"} or payment.verification_status != "Menunggu":
        abort(400)
    accepted = action == "accept"
    if accepted:
        db.session.execute(
            db.select(Vehicle)
            .where(Vehicle.id == payment.rental.vehicle_id)
            .with_for_update()
        ).scalar_one()
        if payment.rental.driver_id:
            db.session.execute(
                db.select(Driver)
                .where(Driver.id == payment.rental.driver_id)
                .with_for_update()
            ).scalar_one()
    if accepted and not vehicle_is_available(
        payment.rental.vehicle_id,
        payment.rental.start_date,
        payment.rental.end_date,
        payment.rental.id,
        lock=True,
    ):
        flash(
            "Pembayaran tidak dapat dikonfirmasi karena jadwal kendaraan bentrok.",
            "danger",
        )
    elif (
        accepted
        and payment.rental.driver_id
        and not driver_is_available(
            payment.rental.driver_id,
            payment.rental.start_date,
            payment.rental.end_date,
            payment.rental.id,
            lock=True,
        )
    ):
        flash(
            "Pembayaran tidak dapat dikonfirmasi karena jadwal pengemudi bentrok.",
            "danger",
        )
    else:
        try:
            notes = limited_text(request.form.get("notes"), "Catatan", maximum=1000)
            verify_payment(payment, current_user, accepted, notes)
            flash(
                (
                    "Pembayaran berhasil diverifikasi."
                    if accepted
                    else "Pembayaran ditolak."
                ),
                "success" if accepted else "warning",
            )
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
    return redirect(url_for("admin.payments"))


@bp.route("/pesanan")
def rentals():
    query = Rental.query
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    return render_template(
        "admin/rentals.html", rentals=query.order_by(Rental.created_at.desc()).all()
    )


@bp.route("/laporan/penyewaan.xlsx")
def export_rentals():
    stream = rentals_excel(Rental.query.order_by(Rental.created_at.desc()).all())
    return send_file(
        stream,
        as_attachment=True,
        download_name="laporan-penyewaan.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
