"""Route autentikasi: login, registrasi, logout, dan perubahan password."""

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    current_user,
    fresh_login_required,
    login_required,
    login_user,
    logout_user,
)
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter
from models import CustomerProfile, User
from services.notification_service import notify
from utils.security import client_fingerprint
from utils.validators import limited_text, normalize_email, password_errors, valid_phone


# Semua URL dalam Blueprint ini otomatis diawali `/auth`.
bp = Blueprint("auth", __name__, url_prefix="/auth")
# Hash tiruan membuat waktu pemeriksaan login gagal tetap relatif seragam,
# sehingga penyerang lebih sulit menebak apakah suatu email terdaftar.
DUMMY_PASSWORD_HASH = generate_password_hash("dummy-password-never-used")


# ==========================================================
# 01. IDENTITAS LOGIN DAN ARAH DASHBOARD
# Menentukan kunci pembatas percobaan login dan halaman tujuan sesuai peran.
# ==========================================================
# Menentukan identitas request untuk pembatasan percobaan login.
def login_identity():
    email = request.form.get("email", "") if request.method == "POST" else ""
    return f"{get_remote_address()}:{client_fingerprint(email)}"


def dashboard_for(user):
    """Menentukan dashboard tujuan berdasarkan peran pengguna."""
    endpoint = {"admin": "admin.dashboard", "petugas": "staff.dashboard"}.get(
        user.role, "customer.dashboard"
    )
    return url_for(endpoint)


# ==========================================================
# 02. LOGIN PENGGUNA
# Memeriksa email dan password, membuat sesi, lalu membuka dashboard.
# ==========================================================
@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"], key_func=login_identity)
@limiter.limit("20 per hour", methods=["POST"])
def login():
    """Memvalidasi kredensial dan membuat sesi pengguna yang sah."""
    if current_user.is_authenticated:
        return redirect(dashboard_for(current_user))
    if request.method == "POST":
        raw_email = request.form.get("email", "")
        try:
            email = normalize_email(raw_email)
        except ValueError:
            email = raw_email.strip().lower()[:190]
        password = request.form.get("password", "")[:129]
        user = User.query.filter_by(email=email).first()
        password_valid = (
            user.check_password(password)
            if user
            else check_password_hash(DUMMY_PASSWORD_HASH, password)
        )
        if user and password_valid and user.is_active:
            session.clear()
            login_user(user, remember=bool(request.form.get("remember")))
            session.permanent = True
            current_app.logger.info(
                "Login berhasil untuk akun %s dari %s",
                client_fingerprint(user.email),
                get_remote_address(),
            )
            flash(f"Selamat datang, {user.name}.", "success")
            return redirect(dashboard_for(user))
        current_app.logger.warning(
            "Login gagal untuk identitas %s dari %s",
            client_fingerprint(email),
            get_remote_address(),
        )
        flash("Email atau password salah.", "danger")
    return render_template("auth/login.html")


# ==========================================================
# 03. REGISTRASI PELANGGAN
# Memvalidasi data pendaftaran lalu membuat akun dan profil pelanggan.
# ==========================================================
@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per hour", methods=["POST"])
def register():
    """Membuat akun pelanggan setelah seluruh input lolos validasi."""
    if current_user.is_authenticated:
        return redirect(dashboard_for(current_user))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        raw_email = request.form.get("email", "")
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        errors = []
        try:
            name = limited_text(name, "Nama", minimum=3, maximum=120, required=True)
            email = normalize_email(raw_email)
        except ValueError as error:
            errors.append(str(error))
            email = raw_email.strip().lower()[:190]
        if email and User.query.filter_by(email=email).first():
            errors.append("Email sudah digunakan.")
        if not valid_phone(phone):
            errors.append("Nomor telepon Indonesia tidak valid.")
        if User.query.filter_by(phone=phone).first():
            errors.append("Nomor telepon sudah digunakan.")
        errors.extend(password_errors(password, personal_values=(name, email, phone)))
        if password != request.form.get("password_confirmation"):
            errors.append("Konfirmasi password tidak cocok.")
        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            user = User(name=name, email=email, phone=phone, role="pelanggan")
            user.set_password(password)
            user.profile = CustomerProfile()
            db.session.add(user)
            db.session.flush()
            notify(
                user.id,
                "Pendaftaran berhasil",
                "Lengkapi profil dan dokumen agar dapat menyewa kendaraan.",
                "/pelanggan/profil",
            )
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash(
                    "Email atau nomor telepon baru saja digunakan akun lain.", "danger"
                )
                return render_template("auth/register.html")
            flash("Registrasi berhasil. Silakan masuk.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html")


# ==========================================================
# 04. KELUAR DARI AKUN
# Mengakhiri login dan membersihkan sesi melalui permintaan POST.
# ==========================================================
@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Menghapus sesi server dan status login pengguna."""
    session.clear()
    logout_user()
    flash("Anda telah keluar.", "info")
    return redirect(url_for("public.home"))


# ==========================================================
# 05. PERUBAHAN PASSWORD
# Memeriksa password lama dan aturan password baru sebelum menyimpannya.
# ==========================================================
@bp.route("/ubah-password", methods=["GET", "POST"])
@fresh_login_required
@limiter.limit("5 per hour", methods=["POST"])
def change_password():
    """Mengganti password hanya dari sesi login yang masih fresh."""
    if request.method == "POST":
        old = request.form.get("old_password", "")
        new = request.form.get("new_password", "")
        if not current_user.check_password(old):
            flash("Password lama salah.", "danger")
        elif password_errors(
            new,
            personal_values=(current_user.name, current_user.email, current_user.phone),
        ):
            for error in password_errors(
                new,
                personal_values=(
                    current_user.name,
                    current_user.email,
                    current_user.phone,
                ),
            ):
                flash(error, "danger")
        elif new != request.form.get("confirmation"):
            flash("Konfirmasi password tidak cocok.", "danger")
        else:
            user = current_user._get_current_object()
            user.set_password(new)
            db.session.commit()
            session.clear()
            login_user(user, fresh=True)
            session.permanent = True
            flash("Password berhasil diperbarui.", "success")
            return redirect(dashboard_for(user))
    return render_template("auth/change_password.html")
