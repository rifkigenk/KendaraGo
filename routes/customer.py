"""Route pelanggan untuk profil, pesanan, pembayaran, dan ulasan."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

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
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from extensions import db, limiter
from models import (
    CustomerProfile,
    Driver,
    Location,
    Payment,
    Rental,
    Review,
    User,
    Vehicle,
)
from services.availability_service import driver_is_available
from services.notification_service import notify
from services.payment_service import (
    PAYMENT_METHODS,
    create_payment,
    payment_method_details,
)
from services.rental_service import cancel_rental, create_rental
from services.report_service import invoice_pdf
from utils.decorators import roles_required
from utils.file_handler import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    delete_upload,
    save_upload,
)
from utils.security import safe_internal_path
from utils.validators import limited_text, valid_phone


# ==========================================================
# 01. AKSES KHUSUS PELANGGAN
# Prefix dan penjaga route membatasi halaman ke pelanggan yang sudah login.
# ==========================================================
bp = Blueprint("customer", __name__, url_prefix="/pelanggan")


@bp.before_request
@login_required
@roles_required("pelanggan")
def guard():
    """Menolak akses jika pengguna bukan pelanggan yang sedang login."""
    pass


# ==========================================================
# 02. DASHBOARD DAN PROFIL
# Menampilkan riwayat pesanan serta mengelola identitas dan dokumen.
# ==========================================================
# Mengambil data ringkasan dan menampilkan dashboard sesuai peran pengguna.
@bp.route("/")
def dashboard():
    rentals = (
        Rental.query.filter_by(customer_id=current_user.id)
        .order_by(Rental.created_at.desc())
        .all()
    )
    return render_template("customer/dashboard.html", rentals=rentals)


# Menampilkan dan memperbarui profil serta dokumen pelanggan.
@bp.route("/profil", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def profile():
    profile = current_user.profile
    new_uploads = []
    if request.method == "POST":
        try:
            name = limited_text(
                request.form.get("name"), "Nama", minimum=3, maximum=120, required=True
            )
            phone = request.form.get("phone", "").strip()
            if not valid_phone(phone):
                raise ValueError("Nomor telepon Indonesia tidak valid.")
            if User.query.filter(
                User.phone == phone, User.id != current_user.id
            ).first():
                raise ValueError("Nomor telepon sudah digunakan akun lain.")
            gender = request.form.get("gender")
            if gender not in {"Laki-laki", "Perempuan"}:
                raise ValueError("Jenis kelamin tidak valid.")
            birth_date = (
                datetime.strptime(request.form["birth_date"], "%Y-%m-%d").date()
                if request.form.get("birth_date")
                else None
            )
            if birth_date and birth_date >= datetime.now().date():
                raise ValueError("Tanggal lahir tidak valid.")
            address = limited_text(
                request.form.get("address"),
                "Alamat",
                maximum=1000,
                required=True,
            )
            ktp_number = "".join(
                filter(str.isdigit, request.form.get("ktp_number", ""))
            )
            if len(ktp_number) != 16:
                raise ValueError("Nomor KTP harus terdiri dari 16 digit.")
            if CustomerProfile.query.filter(
                CustomerProfile.ktp_number == ktp_number,
                CustomerProfile.id != profile.id,
            ).first():
                raise ValueError("Nomor KTP sudah digunakan akun lain.")
            sim_number = limited_text(
                request.form.get("sim_number"),
                "Nomor SIM",
                maximum=32,
                required=True,
            )
            sim_type = request.form.get("sim_type")
            if sim_type not in {"SIM A", "SIM C"}:
                raise ValueError("Jenis SIM tidak valid.")
            emergency_contact = limited_text(
                request.form.get("emergency_contact"),
                "Kontak darurat",
                maximum=100,
            )

            profile_image = ktp_image = sim_image = None
            if request.files.get("profile_image"):
                profile_image = save_upload(
                    request.files["profile_image"], "profiles", IMAGE_EXTENSIONS, True
                )
                new_uploads.append(profile_image)
            if request.files.get("ktp_image"):
                ktp_image = save_upload(
                    request.files["ktp_image"], "documents", IMAGE_EXTENSIONS, True
                )
                new_uploads.append(ktp_image)
            if request.files.get("sim_image"):
                sim_image = save_upload(
                    request.files["sim_image"], "documents", IMAGE_EXTENSIONS, True
                )
                new_uploads.append(sim_image)

            replaced_uploads = []

            current_user.name = name
            current_user.phone = phone
            profile.gender = gender
            profile.birth_date = birth_date
            profile.address = address
            profile.ktp_number = ktp_number
            profile.sim_number = sim_number
            profile.sim_type = sim_type
            profile.emergency_contact = emergency_contact
            if profile_image:
                replaced_uploads.append(profile.profile_image)
                profile.profile_image = profile_image
            if ktp_image:
                replaced_uploads.append(profile.ktp_image)
                profile.ktp_image = ktp_image
            if sim_image:
                replaced_uploads.append(profile.sim_image)
                profile.sim_image = sim_image
            if all(
                [
                    profile.ktp_number,
                    profile.ktp_image,
                    profile.sim_number,
                    profile.sim_type,
                    profile.sim_image,
                    profile.address,
                ]
            ):
                profile.verification_status = "Menunggu verifikasi"
            notify(
                current_user.id,
                "Profil diperbarui",
                "Data dan dokumen profil berhasil disimpan.",
            )
            db.session.commit()
            for old_upload in replaced_uploads:
                delete_upload(old_upload)
            flash("Profil berhasil diperbarui.", "success")
        except (ValueError, KeyError) as error:
            db.session.rollback()
            for new_upload in new_uploads:
                delete_upload(new_upload)
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            for new_upload in new_uploads:
                delete_upload(new_upload)
            flash("Data profil bertabrakan dengan akun lain.", "danger")
    return render_template("customer/profile.html", profile=profile)


# ==========================================================
# 03. PEMBUATAN PESANAN
# Memvalidasi jadwal, lokasi, pengemudi, promo, lalu menyimpan penyewaan.
# ==========================================================
# Memvalidasi permintaan pemesanan sebelum membuat transaksi sewa.
@bp.route("/pesan/<int:vehicle_id>", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def book(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, is_active=True).first_or_404()
    locations = Location.query.filter_by(is_active=True).all()
    drivers = Driver.query.filter_by(is_active=True).all()
    if request.method == "POST":
        try:
            start = datetime.strptime(request.form["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
            pickup_time = datetime.strptime(request.form["pickup_time"], "%H:%M").time()
            pickup_location_id = int(request.form["pickup_location_id"])
            return_location_id = int(request.form["return_location_id"])
            valid_location_ids = {location.id for location in locations}
            if (
                pickup_location_id not in valid_location_ids
                or return_location_id not in valid_location_ids
            ):
                raise ValueError("Lokasi pengambilan atau pengembalian tidak valid.")
            driver = None
            if request.form.get("with_driver"):
                driver = Driver.query.get_or_404(int(request.form["driver_id"]))
                if not driver_is_available(driver.id, start, end):
                    raise ValueError(
                        "Pengemudi tersebut tidak tersedia pada periode yang dipilih."
                    )
            rental = create_rental(
                current_user,
                vehicle,
                start,
                end,
                pickup_time,
                pickup_location_id,
                return_location_id,
                driver,
                request.form.get("promo_code"),
                limited_text(request.form.get("notes"), "Catatan", maximum=1000),
            )
            flash("Pemesanan berhasil dibuat. Silakan lakukan pembayaran.", "success")
            return redirect(url_for("customer.rental_detail", rental_id=rental.id))
        except (ValueError, KeyError) as error:
            db.session.rollback()
            flash(str(error), "danger")
    return render_template(
        "customer/book.html", vehicle=vehicle, locations=locations, drivers=drivers
    )


# ==========================================================
# 04. DETAIL PESANAN
# Pesanan selalu diperiksa agar hanya dapat dibuka oleh pemiliknya.
# ==========================================================
def owned_rental(rental_id):
    """Mengambil pesanan hanya jika pesanan tersebut milik pengguna aktif."""
    return Rental.query.filter_by(
        id=rental_id, customer_id=current_user.id
    ).first_or_404()


# Menampilkan detail transaksi yang dapat diakses pelanggan.
@bp.route("/pesanan/<int:rental_id>")
def rental_detail(rental_id):
    return render_template(
        "customer/rental_detail.html",
        rental=owned_rental(rental_id),
        payment_methods=PAYMENT_METHODS,
    )


# ==========================================================
# 05. PROSES PEMBAYARAN
# Memvalidasi total, metode, pemilik akun, dan bukti sebelum disimpan.
# ==========================================================
# Memproses nominal dan bukti bayar untuk transaksi pelanggan.
@bp.route("/pesanan/<int:rental_id>/bayar", methods=["POST"])
@limiter.limit("5 per hour")
def pay(rental_id):
    # 05A. Pembayaran hanya diterima pada status yang sesuai.
    rental = owned_rental(rental_id)
    if rental.status != "Menunggu pembayaran":
        abort(400)
    proof = None
    try:
        # 05B. Nilai dari form harus sama dengan total resmi di database.
        submitted_amount = Decimal(request.form.get("amount", "0"))
        if submitted_amount != rental.total_payment:
            raise ValueError("Jumlah pembayaran harus sama dengan total tagihan.")
        amount = rental.total_payment
        # 05C. Detail metode menentukan perlu atau tidaknya bukti pembayaran.
        method = request.form.get("method", "")
        method_details = payment_method_details(method)
        account_holder = request.form.get("account_holder", "").strip()
        if method_details["requires_proof"] and not account_holder:
            raise ValueError("Nama pemilik akun atau rekening wajib diisi.")
        proof = save_upload(request.files.get("proof"), "payments", DOCUMENT_EXTENSIONS)
        if method_details["requires_proof"] and not proof:
            raise ValueError("Bukti pembayaran wajib diunggah.")
        # 05D. Pembayaran yang valid disimpan dengan status menunggu verifikasi.
        create_payment(
            rental,
            method,
            account_holder or None,
            amount,
            proof,
        )
        flash("Pembayaran berhasil dikirim untuk diverifikasi.", "success")
    except (ValueError, InvalidOperation) as error:
        delete_upload(proof)
        flash(str(error), "danger")
    return redirect(url_for("customer.rental_detail", rental_id=rental.id))


# ==========================================================
# 06. PEMBATALAN DAN ULASAN
# Pelanggan dapat membatalkan pesanan aktif atau mengulas sewa selesai.
# ==========================================================
# Membatalkan transaksi pelanggan melalui layanan penyewaan.
@bp.route("/pesanan/<int:rental_id>/batal", methods=["POST"])
@limiter.limit("10 per hour")
def cancel(rental_id):
    rental = owned_rental(rental_id)
    try:
        cancel_rental(rental, current_user)
        db.session.commit()
        flash("Pesanan dibatalkan.", "info")
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "danger")
    return redirect(url_for("customer.rental_detail", rental_id=rental.id))


# Menyimpan ulasan pelanggan untuk penyewaan yang memenuhi ketentuan.
@bp.route("/pesanan/<int:rental_id>/ulasan", methods=["POST"])
@limiter.limit("5 per hour")
def review(rental_id):
    rental = owned_rental(rental_id)
    if (
        rental.status != "Selesai"
        or Review.query.filter_by(rental_id=rental.id).first()
    ):
        abort(400)
    rating = request.form.get("rating", type=int)
    if rating not in range(1, 6):
        abort(400)
    try:
        comment = limited_text(request.form.get("comment"), "Ulasan", maximum=1500)
        db.session.add(
            Review(
                customer_id=current_user.id,
                vehicle_id=rental.vehicle_id,
                rental_id=rental.id,
                rating=rating,
                comment=comment,
            )
        )
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "danger")
        return redirect(url_for("customer.rental_detail", rental_id=rental.id))
    flash("Terima kasih atas ulasan Anda.", "success")
    return redirect(url_for("customer.rental_detail", rental_id=rental.id))


# ==========================================================
# 07. INVOICE DAN NOTIFIKASI
# Menyediakan unduhan invoice serta pembaruan status notifikasi.
# ==========================================================
# Menghasilkan unduhan invoice PDF transaksi pelanggan.
@bp.route("/pesanan/<int:rental_id>/invoice.pdf")
def invoice(rental_id):
    rental = owned_rental(rental_id)
    return send_file(
        invoice_pdf(rental),
        mimetype="application/pdf",
        download_name=f"invoice-{rental.booking_code}.pdf",
        as_attachment=True,
    )


# Menandai notifikasi milik pelanggan sebagai sudah dibaca.
@bp.route("/notifikasi/<int:notification_id>", methods=["POST"])
def read_notification(notification_id):
    notification = next(
        (n for n in current_user.notifications if n.id == notification_id), None
    )
    if not notification:
        abort(404)
    notification.is_read = True
    db.session.commit()
    return redirect(
        safe_internal_path(notification.link, url_for("customer.dashboard"))
    )
