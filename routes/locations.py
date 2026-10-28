# ==========================================================
# 01. API LOKASI DAN PENGELOLAAN KANTOR
# Mencari titik di Bali melalui penyedia geocoding dan menyediakan pengaturan kantor untuk admin.
# ==========================================================

"""Authenticated geocoding proxy and admin-managed offices."""

import json
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from functools import lru_cache
from time import time
from urllib.error import URLError

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from extensions import db, limiter
from models import AppSetting, Location
from services.location_service import (
    in_bali,
    office_options,
    primary_office,
    validate_address,
)
from utils.decorators import roles_required

bp = Blueprint("locations", __name__, url_prefix="/lokasi")


# ==========================================================
# 02. PEMERIKSAAN AKUN AKTIF
# Menolak permintaan dari pengguna yang sudah login tetapi akunnya tidak aktif.
# ==========================================================
@bp.before_request
def guard():
    if current_user.is_authenticated and not current_user.is_active:
        return jsonify(error="Akun tidak aktif."), 403


# ==========================================================
# 03. DAFTAR KANTOR UNTUK PEMESANAN
# Mengembalikan kantor terkonfirmasi yang dapat dipilih pada formulir lokasi.
# ==========================================================
@bp.get("/kantor")
def offices():
    return jsonify(offices=office_options())


# ==========================================================
# 04. PENCARIAN ALAMAT MELALUI GEOAPIFY
# Memvalidasi kata pencarian atau koordinat dan beralih ke Photon jika kunci Geoapify belum diisi.
# ==========================================================
@bp.get("/cari")
@limiter.limit("30 per minute")
def search():
    key = current_app.config.get("GEOAPIFY_API_KEY")
    if not key:
        return photon_search()
    params = {"apiKey": key, "format": "json", "lang": "id", "limit": 5}
    reverse = request.args.get("latitude") is not None
    if reverse:
        if not in_bali(request.args.get("latitude"), request.args.get("longitude")):
            return jsonify(error="Titik layanan harus berada di Bali."), 422
        params.update(lat=request.args["latitude"], lon=request.args["longitude"])
        endpoint = "reverse"
    else:
        text = request.args.get("q", "").strip()
        if not 3 <= len(text) <= 200:
            return (
                jsonify(error="Masukkan nama tempat atau alamat (3–200 karakter)."),
                422,
            )
        params.update(
            text=text,
            filter="rect:114.4,-9.1,115.8,-7.9",
            bias="proximity:115.216,-8.65",
        )
        endpoint = "autocomplete"
    try:
        with urlopen(
            "https://api.geoapify.com/v1/geocode/" + endpoint + "?" + urlencode(params),
            timeout=8,
        ) as response:
            results = json.load(response).get("results", [])
    except (URLError, TimeoutError, ValueError, OSError):
        # Do not log the provider URL: it contains the API key and address query.
        return (
            jsonify(
                error="Pencarian tidak tersedia. Coba lagi atau isi alamat dan pin manual."
            ),
            503,
        )
    addresses = []
    for p in results:
        if not in_bali(p.get("lat"), p.get("lon")):
            continue
        addresses.append(
            {
                "place_name": p.get("name") or p.get("address_line1", ""),
                "street": p.get("street", ""),
                "building_number": p.get("housenumber", ""),
                "village": p.get("suburb", ""),
                "district": p.get("district", ""),
                "city": p.get("city") or p.get("county", ""),
                "province": "Bali",
                "postcode": p.get("postcode", ""),
                "latitude": p["lat"],
                "longitude": p["lon"],
                "formatted": p.get("formatted", ""),
            }
        )
    return jsonify(
        results=addresses,
        attribution="Powered by Geoapify | © OpenStreetMap contributors",
    )


# ==========================================================
# 05. CACHE HASIL PENCARIAN PHOTON
# Mengambil hasil penyedia dan memakai parameter periode untuk membatasi masa cache.
# ==========================================================
@lru_cache(maxsize=256)
def photon_results(query, reverse, cache_period):
    endpoint = "reverse" if reverse else "api"
    req = Request(
        f"https://photon.komoot.io/{endpoint}/?{query}",
        headers={"User-Agent": "KendaraGo/1.0 (Bali rental location search)"},
    )
    with urlopen(req, timeout=8) as response:
        return json.load(response).get("features", [])


# ==========================================================
# 06. PENCARIAN ALTERNATIF MELALUI PHOTON
# Memproses pencarian tempat atau koordinat dan menyaring hasil agar berada di Bali.
# ==========================================================
def photon_search():
    reverse = request.args.get("latitude") is not None
    if reverse:
        if not in_bali(request.args.get("latitude"), request.args.get("longitude")):
            return jsonify(error="Titik layanan harus berada di Bali."), 422
        params = dict(
            lat=request.args["latitude"], lon=request.args["longitude"], limit=1
        )
    else:
        query = request.args.get("q", "").strip()
        if not 3 <= len(query) <= 200:
            return jsonify(error="Ketik nama tempat minimal 3 karakter."), 422
        params = dict(
            q=query, limit=5, bbox="114.4,-9.1,115.8,-7.9", lat=-8.65, lon=115.216
        )
    try:
        features = photon_results(urlencode(params), reverse, int(time() // 600))
    except (URLError, TimeoutError, ValueError, OSError):
        return (
            jsonify(
                error="Pencarian sedang tidak tersedia. Pilih titik di peta dan isi nama tempat secara manual."
            ),
            503,
        )
    addresses = []
    for feature in features:
        lon, lat = feature["geometry"]["coordinates"][:2]
        if not in_bali(lat, lon):
            continue
        p = feature.get("properties", {})
        name = p.get("name") or p.get("street") or p.get("city") or "Titik temu"
        formatted = ", ".join(
            dict.fromkeys(
                filter(
                    None,
                    [name, p.get("street"), p.get("district"), p.get("city"), "Bali"],
                )
            )
        )
        addresses.append(
            dict(
                place_name=name,
                street=p.get("street", ""),
                city=p.get("city", ""),
                province="Bali",
                latitude=lat,
                longitude=lon,
                formatted=formatted,
            )
        )
    return jsonify(
        results=addresses, attribution="Photon / © OpenStreetMap contributors"
    )


# ==========================================================
# 07. HALAMAN PENGATURAN KANTOR
# Menampilkan kantor utama kepada admin untuk pemeriksaan dan perubahan alamat.
# ==========================================================
@bp.get("/admin")
@roles_required("admin")
def manage():
    return render_template("admin/locations.html", office=primary_office())


# ==========================================================
# 08. MENYIMPAN KANTOR UTAMA
# Memvalidasi alamat dan versi data, lalu menyimpan kantor serta pengaturan kantor utama.
# ==========================================================
@bp.post("/admin")
@roles_required("admin")
def save_office():
    data = request.get_json(silent=True) or {}
    try:
        address = validate_address(data.get("address"), office_admin=True)
        if address["kind"] != "office":
            raise ValueError("Jenis lokasi harus kantor rental.")
        primary = primary_office()
        if data.get("id") and (primary is None or data["id"] != primary.id):
            return (
                jsonify(error="Hanya kantor utama Denpasar yang dapat dikelola."),
                422,
            )
        office = (
            Location.query.filter_by(id=primary.id).with_for_update().first()
            if primary
            else Location()
        )
        if office.id and data.get("version") != office.updated_at.isoformat():
            return (
                jsonify(error="Data kantor berubah. Muat ulang sebelum menyimpan."),
                409,
            )
        office.name = address["place_name"]
        if len(office.name) > 120:
            raise ValueError("Nama kantor maksimal 120 karakter.")
        office.address = address["formatted"]
        office.address_data = address
        office.is_active = data.get("active") is True
        office.verified_by_id = current_user.id
        db.session.add(office)
        db.session.flush()
        setting = AppSetting.query.filter_by(setting_key="primary_office_id").first()
        if setting is None:
            setting = AppSetting(
                setting_key="primary_office_id", description="Kantor utama rental Bali"
            )
            db.session.add(setting)
        setting.setting_value = str(office.id)
        db.session.commit()
        return jsonify(message="Alamat kantor berhasil disimpan.", id=office.id)
    except (ValueError, TypeError, IntegrityError):
        db.session.rollback()
        return (
            jsonify(
                error="Gagal menyimpan. Periksa alamat Bali, konfirmasi pin, dan nama kantor yang unik."
            ),
            422,
        )
