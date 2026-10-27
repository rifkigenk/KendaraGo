# ==========================================================
# 01. CONFIG
# Konfigurasi aplikasi yang nilainya dapat diubah melalui berkas `.env`.
# ==========================================================

"""Konfigurasi aplikasi yang nilainya dapat diubah melalui berkas `.env`."""

import os
from hashlib import sha256
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


# BASE_DIR selalu menunjuk folder proyek sehingga path tidak bergantung pada
# lokasi terminal saat aplikasi dijalankan.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_WHATSAPP_NUMBER = "6282282026127"


def env_bool(name, default=False):
    """Mengubah teks environment seperti `true` atau `1` menjadi boolean."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default):
    """Mengubah environment dipisah koma menjadi list yang sudah dirapikan."""
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()] or default


def normalize_whatsapp_number(value):
    """Mengubah nomor telepon ke format internasional yang diminta wa.me."""
    digits = "".join(filter(str.isdigit, value or ""))
    if digits.startswith("0"):
        return f"62{digits[1:]}"
    return digits or DEFAULT_WHATSAPP_NUMBER


def local_phone_number(value):
    """Mengubah nomor internasional ke format lokal untuk ditampilkan."""
    return f"0{value[2:]}" if value.startswith("62") else value


class Config:
    """Konfigurasi utama untuk aplikasi lokal maupun produksi."""

    # Pengaturan dasar Flask dan perlindungan formulir CSRF.
    DEBUG = env_bool("FLASK_DEBUG", False)
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    SECRET_KEY = os.getenv("SECRET_KEY")
    WTF_CSRF_SECRET_KEY = os.getenv("WTF_CSRF_SECRET_KEY") or (
        sha256(f"{SECRET_KEY}:csrf".encode()).hexdigest() if SECRET_KEY else None
    )
    WTF_CSRF_TIME_LIMIT = 1800
    WTF_CSRF_SSL_STRICT = True
    WTF_CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    # Nomor disimpan dalam dua bentuk: untuk tautan wa.me dan untuk tampilan.
    WHATSAPP_NUMBER = normalize_whatsapp_number(
        os.getenv("WHATSAPP_NUMBER", DEFAULT_WHATSAPP_NUMBER)
    )
    WHATSAPP_DISPLAY_NUMBER = local_phone_number(WHATSAPP_NUMBER)
    WHATSAPP_ENABLED = env_bool("WHATSAPP_ENABLED", False)
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "")
    WHATSAPP_PUBLIC_URL = os.getenv("WHATSAPP_PUBLIC_URL", "")
    WHATSAPP_TEMPLATE_NAME = os.getenv("WHATSAPP_TEMPLATE_NAME", "")
    WHATSAPP_TEMPLATE_LANGUAGE = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "id")

    # SQLAlchemy membaca URL koneksi MySQL dari environment.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://root:@localhost/db_kendarago"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    # Batas request dan form mencegah unggahan yang terlalu besar.
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 2 * 1024 * 1024))
    MAX_FORM_MEMORY_SIZE = int(os.getenv("MAX_FORM_MEMORY_SIZE", 256 * 1024))
    MAX_FORM_PARTS = int(os.getenv("MAX_FORM_PARTS", 100))
    # Cookie sesi dibuat HttpOnly dan SameSite agar lebih sulit disalahgunakan.
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_NAME = "kendarago_session"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_PATH = "/"
    # Foto kendaraan boleh publik, sedangkan dokumen identitas disimpan privat.
    PUBLIC_UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
    PRIVATE_UPLOAD_FOLDER = BASE_DIR / "instance" / "private_uploads"
    UPLOAD_FOLDER = PUBLIC_UPLOAD_FOLDER
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 2 * 1024 * 1024))
    # Host, HTTPS, dan rate limit dapat diperketat saat aplikasi dipublikasikan.
    TRUSTED_HOSTS = env_list("TRUSTED_HOSTS", ["127.0.0.1", "localhost", "::1"])
    FORCE_HTTPS = env_bool("FORCE_HTTPS", False)
    # Tetap aktif secara default untuk produksi, tetapi dapat dimatikan lewat
    # .env saat pengembangan lokal agar pengujian formulir tidak terkunci.
    RATELIMIT_ENABLED = env_bool("RATELIMIT_ENABLED", True)
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_DEFAULT = "300 per minute"
    RATELIMIT_META = "10 per hour; 50 per day"
    ITEMS_PER_PAGE = 9
    PAYMENT_DEADLINE_HOURS = int(os.getenv("PAYMENT_DEADLINE_HOURS", 2))
    APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Jakarta")
    GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "")
    MAP_TILES_ENABLED = env_bool("MAP_TILES_ENABLED", True)
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    GOOGLE_MAPS_MAP_ID = (
        os.getenv("GOOGLE_MAPS_MAP_ID", "DEMO_MAP_ID").strip() or "DEMO_MAP_ID"
    )


class TestingConfig(Config):
    """Konfigurasi ringan untuk test tanpa MySQL dan tanpa token CSRF."""

    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    RATELIMIT_ENABLED = False
    TRUSTED_HOSTS = None
