# ==========================================================
# 01. VALIDASI TITIK TEMU DI BALI
# Memeriksa batas wilayah dari GeoJSON dan membentuk salinan alamat kantor atau titik pilihan penyewa.
# ==========================================================

"""Bali-only meeting points, independent of a geocoding provider or browser input."""

import json
import math
from functools import lru_cache
from pathlib import Path

from models import AppSetting, Location

FIELDS = {
    "place_name": 180,
    "street": 250,
    "building_number": 40,
    "village": 120,
    "district": 120,
    "city": 120,
    "province": 40,
    "postcode": 12,
    "instructions": 1000,
}
KINDS = {"office", "airport", "hotel", "other"}


# ==========================================================
# 02. MEMUAT BATAS WILAYAH
# Membaca geometri Bali dari berkas GeoJSON lokal dan menyimpan hasilnya dalam cache.
# ==========================================================
@lru_cache(maxsize=1)
def bali_geometry():
    return json.loads(
        (Path(__file__).resolve().parents[1] / "static/data/bali.geojson").read_text(
            encoding="utf-8"
        )
    )["geometry"]


# ==========================================================
# 03. PEMERIKSAAN TITIK DALAM POLIGON
# Menghitung persilangan garis untuk menentukan apakah koordinat berada di dalam satu cincin batas.
# ==========================================================
def in_ring(x, y, ring):
    inside = False
    for a, b in zip(ring, ring[1:]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                inside = not inside
    return inside


# ==========================================================
# 04. PEMERIKSAAN CAKUPAN LAYANAN
# Menolak koordinat tidak valid dan memeriksa poligon Bali beserta area lubang di dalamnya.
# ==========================================================
def in_bali(latitude, longitude):
    try:
        lat, lon = float(latitude), float(longitude)
    except (ValueError, TypeError):
        return False
    if not math.isfinite(lat) or not math.isfinite(lon):
        return False
    geometry = bali_geometry()
    polygons = (
        geometry["coordinates"]
        if geometry["type"] == "MultiPolygon"
        else [geometry["coordinates"]]
    )
    return any(
        in_ring(lon, lat, p[0]) and not any(in_ring(lon, lat, h) for h in p[1:])
        for p in polygons
    )


# ==========================================================
# 05. PENYUSUNAN ALAMAT TAMPILAN
# Menggabungkan bagian alamat yang terisi menjadi teks ringkas untuk pengguna.
# ==========================================================
def format_address(data):
    street = " ".join(filter(None, [data.get("street"), data.get("building_number")]))
    return ", ".join(
        filter(
            None,
            [
                data.get("place_name"),
                street,
                data.get("village"),
                data.get("district"),
                data.get("city"),
                "Bali",
                data.get("postcode"),
            ],
        )
    )


# ==========================================================
# 06. VALIDASI DAN SALINAN ALAMAT
# Memeriksa konfirmasi, jenis, isi, dan koordinat; alamat kantor diambil dari data admin yang berlaku.
# ==========================================================
def validate_address(raw, *, office_admin=False):
    if not isinstance(raw, dict) or raw.get("confirmed") is not True:
        raise ValueError("Periksa alamat dan konfirmasi titik temu terlebih dahulu.")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise ValueError("Pilih jenis lokasi yang valid.")
    if kind == "office" and not office_admin:
        office = Location.query.filter_by(
            id=raw.get("office_id"), is_active=True
        ).first()
        primary = primary_office()
        if (
            not office
            or not primary
            or office.id != primary.id
            or not office.verified_by_id
            or not office.address_data
        ):
            raise ValueError("Kantor belum dikonfirmasi admin atau sudah tidak aktif.")
        # Never trust a submitted office address: snapshot the admin's current record.
        if raw.get("office_updated_at") != office.updated_at.isoformat():
            raise ValueError(
                "Alamat kantor diperbarui admin. Muat ulang dan konfirmasi kembali."
            )
        result = validate_address(
            {**office.address_data, "kind": "office", "confirmed": True},
            office_admin=True,
        )
        result.update(
            office_id=office.id, office_updated_at=office.updated_at.isoformat()
        )
        instructions = raw.get("instructions", "")
        if not isinstance(instructions, str) or len(instructions) > 1000:
            raise ValueError("Instruksi penjemputan maksimal 1000 karakter.")
        result["instructions"] = instructions.strip()
        return result
    data = {"kind": kind, "confirmed": True}
    for field, limit in FIELDS.items():
        value = raw.get(field, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"Isian {field} tidak valid atau terlalu panjang.")
        data[field] = value.strip()
    if data["province"].casefold() != "bali" or not in_bali(
        raw.get("latitude"), raw.get("longitude")
    ):
        raise ValueError(
            "Titik layanan harus berada di wilayah Bali. Periksa pin peta."
        )
    if not data["place_name"]:
        raise ValueError("Isi nama tempat atau titik temu.")
    data["province"] = "Bali"
    data["latitude"] = round(float(raw["latitude"]), 7)
    data["longitude"] = round(float(raw["longitude"]), 7)
    data["formatted"] = format_address(data)
    return data


# ==========================================================
# 07. PEMILIHAN KANTOR UTAMA
# Membaca pengaturan kantor utama dengan cadangan lokasi Denpasar atau kantor terverifikasi di Bali.
# ==========================================================
def primary_office():
    """Select the single Bali office; retain legacy locations for old rentals."""
    setting = AppSetting.query.filter_by(setting_key="primary_office_id").first()
    if setting:
        try:
            return Location.query.filter_by(id=int(setting.setting_value)).first()
        except (TypeError, ValueError):
            return None
    denpasar = Location.query.filter_by(name="Denpasar").first()
    if denpasar:
        return denpasar
    for office in Location.query.filter(Location.verified_by_id.is_not(None)).order_by(
        Location.id
    ):
        address = office.address_data or {}
        if in_bali(address.get("latitude"), address.get("longitude")):
            return office
    return None


# ==========================================================
# 08. KANTOR YANG BISA DIPESAN
# Menyertakan kantor utama hanya jika aktif, terverifikasi, memiliki alamat, dan berada di Bali.
# ==========================================================
def bookable_offices():
    office = primary_office()
    if office and office.is_active and office.verified_by_id and office.address_data:
        if in_bali(
            office.address_data.get("latitude"), office.address_data.get("longitude")
        ):
            return [office]
    return []


# ==========================================================
# 09. DATA PILIHAN KANTOR
# Membentuk ID, nama, alamat, dan versi waktu untuk pilihan kantor pada formulir.
# ==========================================================
def office_options():
    return [
        {
            "id": o.id,
            "name": o.name,
            "address": o.address_data,
            "updated_at": o.updated_at.isoformat(),
        }
        for o in bookable_offices()
        if in_bali(o.address_data.get("latitude"), o.address_data.get("longitude"))
    ]
