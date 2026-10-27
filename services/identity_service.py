"""Validate booking identity format and keep a snapshot for authorized staff."""

import re


IDENTITY_LABELS = {"NIK": "NIK / KTP", "NISN": "NISN", "PASSPORT": "Paspor"}


def validate_identity(kind, number, country=""):
    if kind not in IDENTITY_LABELS:
        raise ValueError("Pilih jenis identitas: NIK / KTP, NISN, atau paspor.")
    if not isinstance(number, str) or len(number) > 32:
        raise ValueError("Nomor identitas tidak valid.")
    number = number.strip().upper()
    if kind == "NIK" and not re.fullmatch(r"[0-9]{16}", number):
        raise ValueError("NIK harus berisi tepat 16 angka sesuai KTP.")
    if kind == "NISN" and not re.fullmatch(r"[0-9]{10}", number):
        raise ValueError("NISN harus berisi tepat 10 angka.")
    if kind == "PASSPORT":
        if not re.fullmatch(r"[A-Z0-9]{5,20}", number):
            raise ValueError("Nomor paspor harus berisi 5–20 huruf atau angka.")
        if not isinstance(country, str) or not 2 <= len(country.strip()) <= 80:
            raise ValueError("Isi negara penerbit paspor (2–80 karakter).")
        if any(ord(char) < 32 for char in country):
            raise ValueError("Negara penerbit paspor tidak valid.")
        country = country.strip()
    else:
        country = "Indonesia"
    return {"type": kind, "number": number, "country": country}


def normalize_booking_phone(value):
    """Accept Indonesian local mobiles and international numbers with country code."""
    if not isinstance(value, str) or len(value) > 32:
        raise ValueError("Nomor WhatsApp tidak valid.")
    phone = re.sub(r"[\s()-]", "", value)
    if re.fullmatch(r"(?:\+62|62|0)8[1-9][0-9]{6,11}", phone):
        return phone
    if re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
        return phone
    raise ValueError(
        "Gunakan nomor Indonesia atau kode negara, misalnya 081234567890 atau +447123456789."
    )
