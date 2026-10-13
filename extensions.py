"""Objek extension Flask yang dipakai bersama oleh seluruh modul aplikasi."""

from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect


# Objek belum diikat ke aplikasi di sini. Pengikatan dilakukan oleh
# `init_app()` di application factory supaya modul aman untuk diimpor ulang.
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address)


# Jika pengguna belum login, Flask-Login mengarahkannya ke endpoint ini.
login_manager.login_view = "auth.login"
login_manager.login_message = "Silakan masuk untuk mengakses halaman tersebut."
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"
