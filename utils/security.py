# ==========================================================
# 01. SECURITY
# Konfigurasi keamanan HTTP, CSP, fingerprint, dan redirect internal.
# ==========================================================

"""Konfigurasi keamanan HTTP, CSP, fingerprint, dan redirect internal."""

from hashlib import sha256
from secrets import token_urlsafe
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app, g, request


INSECURE_SECRETS = {
    "change-me",
    "dev-secret-change-me",
    "ganti_dengan_hasil_secrets_token_hex_32",
    "ganti_dengan_secret_csrf_acak_yang_berbeda",
    "ganti_dengan_secret_key",
    "secret",
}


# Memvalidasi secret, HTTPS, tenggat, zona waktu, dan konfigurasi produksi.
def validate_security_config(app):
    secret = app.config.get("SECRET_KEY") or ""
    if len(secret) < 32 or secret.lower() in INSECURE_SECRETS:
        raise RuntimeError(
            "SECRET_KEY wajib berupa nilai acak minimal 32 karakter. "
            'Buat dengan: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    csrf_secret = app.config.get("WTF_CSRF_SECRET_KEY") or ""
    if len(csrf_secret) < 32 or csrf_secret.lower() in INSECURE_SECRETS:
        raise RuntimeError(
            "WTF_CSRF_SECRET_KEY wajib berupa nilai acak minimal 32 karakter."
        )
    if app.config.get("FORCE_HTTPS") and not app.config.get("SESSION_COOKIE_SECURE"):
        raise RuntimeError("SESSION_COOKIE_SECURE wajib aktif saat FORCE_HTTPS aktif.")
    if not 1 <= app.config.get("PAYMENT_DEADLINE_HOURS", 0) <= 168:
        raise RuntimeError("PAYMENT_DEADLINE_HOURS harus berada antara 1 dan 168 jam.")
    try:
        ZoneInfo(app.config.get("APP_TIMEZONE", ""))
    except ZoneInfoNotFoundError as error:
        raise RuntimeError("APP_TIMEZONE tidak valid.") from error
    if app.config.get("APP_ENV") == "production":
        if not app.config.get("FORCE_HTTPS"):
            raise RuntimeError("FORCE_HTTPS wajib aktif pada environment production.")
        if app.config.get("RATELIMIT_STORAGE_URI") == "memory://":
            raise RuntimeError(
                "RATELIMIT_STORAGE_URI production harus memakai penyimpanan bersama."
            )


# Menyimpan token acak per request untuk izin script pada kebijakan CSP.
def create_csp_nonce():
    g.csp_nonce = token_urlsafe(24)


# Memasang kebijakan CSP, pembatasan browser, dan kontrol cache respons HTML.
def apply_security_headers(response):
    nonce = getattr(g, "csp_nonce", "")
    google_enabled = bool(current_app.config.get("GOOGLE_MAPS_API_KEY"))
    google_scripts = (
        " https://maps.googleapis.com https://maps.gstatic.com 'unsafe-eval'"
        if google_enabled
        else ""
    )
    google_assets = (
        " https://*.googleapis.com https://*.gstatic.com https://*.google.com https://*.googleusercontent.com"
        if google_enabled
        else ""
    )
    google_fonts = " https://fonts.gstatic.com" if google_enabled else ""
    google_styles = " https://fonts.googleapis.com" if google_enabled else ""
    policy = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        f"script-src 'self' 'nonce-{nonce}'{google_scripts}; "
        f"style-src 'self' 'unsafe-inline'{google_styles}; "
        f"img-src 'self' data: blob: https://tile.openstreetmap.org{google_assets}; "
        f"font-src 'self'{google_fonts}; "
        f"connect-src 'self' data: blob:{google_assets}; "
        f"frame-src 'self'{(' https://*.google.com' if google_enabled else '')}; "
        "media-src 'self'; "
        "worker-src 'self' blob:; "
        "manifest-src 'self'"
    )
    if current_app.config.get("FORCE_HTTPS"):
        policy += "; upgrade-insecure-requests"
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
    response.headers["Content-Security-Policy"] = policy
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(self), payment=(), usb=(), "
        "interest-cohort=()"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    if response.mimetype in {"text/html", "application/json"}:
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


# Meringkas identitas yang dinormalisasi menjadi 12 karakter hash SHA-256.
def client_fingerprint(value):
    return sha256((value or "").strip().lower().encode()).hexdigest()[:12]


def safe_internal_path(value, fallback="/"):
    """Only allow absolute paths on this application, never external redirects."""
    parsed = urlsplit(value or "")
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return fallback
    if parsed.path.startswith("//") or "\\" in parsed.path:
        return fallback
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


# Memeriksa HTTPS request atau kewajiban HTTPS dalam konfigurasi.
def request_is_secure():
    return request.is_secure or current_app.config.get("FORCE_HTTPS", False)
