"""Titik masuk aplikasi dan tempat seluruh komponen Flask dirangkai."""

from pathlib import Path, PurePosixPath
from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask, g, render_template, request
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import SecurityError, TooManyRequests

from config import Config
from extensions import csrf, db, limiter, login_manager, migrate
from utils.security import (
    apply_security_headers,
    create_csp_nonce,
    validate_security_config,
)


# ==========================================================
# 01. MEMBUAT APLIKASI FLASK
# Menyiapkan konfigurasi dan extension sebelum fitur didaftarkan.
# ==========================================================
def create_app(config_class=Config):
    """Membuat satu aplikasi Flask lengkap berdasarkan kelas konfigurasi."""

    # Pola application factory membuat konfigurasi produksi dan pengujian
    # dapat memakai susunan aplikasi yang sama.
    app = Flask(__name__)
    app.config.from_object(config_class)
    validate_security_config(app)

    # Extension dibuat tanpa aplikasi di extensions.py, kemudian dihubungkan
    # di sini agar tidak terjadi circular import antar-modul.
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Import diletakkan di dalam factory setelah extension siap. Dengan cara
    # ini model dan route boleh mengimpor `db` tanpa saling mengunci saat start.
    from models import User
    from routes.admin import bp as admin_bp
    from routes.auth import bp as auth_bp
    from routes.customer import bp as customer_bp
    from routes.files import bp as files_bp
    from routes.public import bp as public_bp
    from routes.staff import bp as staff_bp

    # ==========================================================
    # 02. PENDAFTARAN MODUL FITUR
    # Menghubungkan routes publik, akun, pelanggan, berkas, petugas, dan admin.
    # ==========================================================
    # Blueprint memecah URL berdasarkan tanggung jawab dan peran pengguna.
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_bp)
    from routes.whatsapp import bp as whatsapp_bp
    from services.whatsapp_service import send_pending
    from urllib.parse import urlsplit

    if app.config["WHATSAPP_ENABLED"]:
        required = (
            "WHATSAPP_APP_SECRET",
            "WHATSAPP_VERIFY_TOKEN",
            "WHATSAPP_PHONE_NUMBER_ID",
            "WHATSAPP_ACCESS_TOKEN",
            "WHATSAPP_API_VERSION",
        )
        if not all(app.config[key] for key in required):
            raise ValueError("Lengkapi konfigurasi Meta sebelum mengaktifkan WhatsApp.")
        public_url = urlsplit(app.config["WHATSAPP_PUBLIC_URL"])
        if (
            public_url.scheme != "https"
            or not public_url.hostname
            or public_url.username
        ):
            raise ValueError("WHATSAPP_PUBLIC_URL harus berupa URL HTTPS publik.")
    app.register_blueprint(whatsapp_bp)
    app.cli.add_command(send_pending)

    @login_manager.user_loader
    def load_user(user_id):
        """Mengambil kembali pengguna dari ID yang tersimpan di sesi login."""
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    # Membuat nonce CSP dan menutup reservasi kedaluwarsa sebelum request non-statis.
    @app.before_request
    def prepare_security_context():
        # Nonce baru pada setiap request mengizinkan script yang sah di CSP.
        create_csp_nonce()
        if request.endpoint == "static" or request.blueprint == "whatsapp":
            return
        from services.rental_service import expire_unpaid_rentals

        expire_unpaid_rentals()

    # Memasang header keamanan pada respons sebelum dikirim ke browser.
    @app.after_request
    def secure_response(response):
        # Header keamanan dipasang pada semua respons, termasuk halaman error.
        return apply_security_headers(response)

    @app.context_processor
    def globals_context():
        """Menyediakan data global yang dapat dipakai oleh semua template."""
        unread_count = 0
        if current_user.is_authenticated:
            unread_count = sum(
                1 for item in current_user.notifications if not item.is_read
            )

        # Memastikan foto berada di folder unggahan publik atau memakai gambar cadangan.
        def vehicle_image_path(vehicle):
            relative = PurePosixPath(vehicle.main_image or "")
            upload_root = Path(app.config["PUBLIC_UPLOAD_FOLDER"]).resolve()
            target = (upload_root / Path(*relative.parts)).resolve()
            if (
                relative.parts
                and not relative.is_absolute()
                and ".." not in relative.parts
                and upload_root in target.parents
                and target.is_file()
            ):
                return f"uploads/{relative.as_posix()}"
            return "uploads/vehicles/adventure-bike-green.png"

        # Mengubah waktu UTC database ke zona waktu aplikasi sebelum ditampilkan.
        def local_datetime(value, format_string="%d/%m/%Y %H:%M"):
            if value is None:
                return "-"
            aware = (
                value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
            )
            return aware.astimezone(ZoneInfo(app.config["APP_TIMEZONE"])).strftime(
                format_string
            )

        return {
            "unread_count": unread_count,
            "csp_nonce": g.get("csp_nonce", ""),
            "vehicle_image_path": vehicle_image_path,
            "local_datetime": local_datetime,
        }

    @app.cli.command("expire-rentals")
    def expire_rentals_command():
        """Menutup reservasi yang melewati tenggat pembayaran."""
        from services.rental_service import expire_unpaid_rentals

        count = expire_unpaid_rentals()
        print(f"{count} pesanan kedaluwarsa ditutup.")

    # Mencatat penolakan CSRF dan mengembalikan halaman kesalahan 400.
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        app.logger.warning(
            "Permintaan ditolak oleh proteksi CSRF: %s", error.description
        )
        return render_template("errors/error.html", code=400), 400

    # Mencatat batas request yang terlampaui dan mengembalikan halaman 429.
    @app.errorhandler(TooManyRequests)
    def rate_limit_error(error):
        app.logger.warning("Batas request terlampaui pada endpoint %s", error.name)
        return render_template("errors/error.html", code=429), 429

    # Menolak header Host yang tidak sesuai konfigurasi aplikasi.
    @app.errorhandler(SecurityError)
    def untrusted_host(error):
        app.logger.warning("Permintaan dengan Host tidak tepercaya ditolak")
        return "Permintaan ditolak.", 400, {"Content-Type": "text/plain; charset=utf-8"}

    # Satu template error dipakai ulang untuk beberapa kode HTTP.
    # `code=code` pada lambda menyimpan nilai tiap putaran dengan benar.
    for code in (400, 401, 403, 404, 413, 500):
        app.register_error_handler(
            code,
            lambda error, code=code: (
                render_template("errors/error.html", code=code),
                code,
            ),
        )

    # Folder unggahan dibuat otomatis jika belum tersedia.
    Path(app.config["PUBLIC_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["PRIVATE_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    return app


# Objek ini dicari oleh perintah `flask` maupun server WSGI.
app = create_app()


if __name__ == "__main__":
    # Blok ini hanya berjalan saat file dieksekusi langsung: `python app.py`.
    app.run(host="127.0.0.1", port=5000, debug=app.config["DEBUG"])
