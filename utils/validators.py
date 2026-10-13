"""Validator terpusat agar aturan input konsisten di semua formulir."""

import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from email_validator import EmailNotValidError, validate_email


PHONE_PATTERN = re.compile(r"^(?:\+62|62|0)8[1-9][0-9]{6,11}$")
COMMON_PASSWORDS = {
    "123456789012345",
    "admin1234567890",
    "kendarago123456",
    "password1234567",
    "qwerty123456789",
}


def valid_phone(value):
    """Memeriksa pola nomor seluler Indonesia setelah spasi/tanda hubung dibuang."""
    return bool(
        PHONE_PATTERN.fullmatch((value or "").replace(" ", "").replace("-", ""))
    )


def normalize_email(value):
    """Memvalidasi lalu menyeragamkan email menjadi huruf kecil."""
    if not value or len(value) > 190:
        raise ValueError("Alamat email tidak valid.")
    try:
        result = validate_email(value.strip(), check_deliverability=False)
    except EmailNotValidError as error:
        raise ValueError("Alamat email tidak valid.") from error
    return result.normalized.lower()


def password_errors(password, *, personal_values=()):
    """Mengembalikan daftar masalah keamanan password tanpa langsung gagal."""
    errors = []
    if len(password) < 15:
        errors.append("Password minimal 15 karakter.")
    if len(password) > 128:
        errors.append("Password maksimal 128 karakter.")
    if "\x00" in password or "\r" in password or "\n" in password:
        errors.append("Password mengandung karakter kontrol yang tidak diizinkan.")
    lowered = password.casefold()
    if lowered in COMMON_PASSWORDS:
        errors.append("Password terlalu umum dan mudah ditebak.")
    for value in personal_values:
        candidate = (value or "").strip().casefold()
        if len(candidate) >= 4 and candidate in lowered:
            errors.append(
                "Password tidak boleh memuat nama, email, atau nomor telepon."
            )
            break
    return errors


def limited_text(value, field, *, maximum, minimum=0, required=False):
    """Membersihkan teks dan memastikan panjangnya berada dalam batas."""
    text = (value or "").strip()
    if required and not text:
        raise ValueError(f"{field} wajib diisi.")
    if len(text) < minimum:
        raise ValueError(f"{field} minimal {minimum} karakter.")
    if len(text) > maximum:
        raise ValueError(f"{field} maksimal {maximum} karakter.")
    if "\x00" in text:
        raise ValueError(f"{field} mengandung karakter yang tidak valid.")
    return text


def decimal_amount(
    value, field, *, minimum=Decimal("0"), maximum=Decimal("1000000000")
):
    """Mengubah input menjadi Decimal dan menolak nilai di luar batas."""
    try:
        amount = Decimal(str(value or "0"))
    except InvalidOperation as error:
        raise ValueError(f"{field} tidak valid.") from error
    if not amount.is_finite() or amount < minimum or amount > maximum:
        raise ValueError(f"{field} berada di luar batas yang diizinkan.")
    return amount


def bounded_int(value, field, *, minimum=0, maximum=10_000_000):
    """Mengubah input menjadi integer yang berada dalam rentang aman."""
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} tidak valid.") from error
    if number < minimum or number > maximum:
        raise ValueError(f"{field} berada di luar batas yang diizinkan.")
    return number


def safe_http_url(value, field="URL"):
    """Menerima URL absolut hanya dengan protokol HTTP atau HTTPS."""
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) > 500:
        raise ValueError(f"{field} terlalu panjang.")
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} harus menggunakan http atau https.")
    return text
