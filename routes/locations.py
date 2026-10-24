"""Authenticated geocoding proxy and admin-managed offices."""
import json
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from extensions import db, limiter
from models import Location
from services.location_service import in_bali, office_options, validate_address
from utils.decorators import roles_required

bp = Blueprint("locations", __name__, url_prefix="/lokasi")


@bp.before_request
@roles_required("admin", "pelanggan")
def guard():
    if not current_user.is_active:
        return jsonify(error="Akun tidak aktif."), 403


@bp.get("/kantor")
def offices():
    return jsonify(offices=office_options())


@bp.get("/cari")
@limiter.limit("30 per minute")
def search():
    key = current_app.config.get("GEOAPIFY_API_KEY")
    if not key:
        return jsonify(error="Pencarian alamat belum terhubung. Isi alamat dan pin secara manual."), 503
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
            return jsonify(error="Masukkan nama tempat atau alamat (3–200 karakter)."), 422
        params.update(text=text, filter="rect:114.4,-9.1,115.8,-7.9", bias="proximity:115.216,-8.65")
        endpoint = "autocomplete"
    try:
        with urlopen("https://api.geoapify.com/v1/geocode/" + endpoint + "?" + urlencode(params), timeout=8) as response:
            results = json.load(response).get("results", [])
    except (URLError, TimeoutError, ValueError, OSError):
        # Do not log the provider URL: it contains the API key and address query.
        return jsonify(error="Pencarian tidak tersedia. Coba lagi atau isi alamat dan pin manual."), 503
    addresses = []
    for p in results:
        if not in_bali(p.get("lat"), p.get("lon")):
            continue
        addresses.append({
            "place_name": p.get("name") or p.get("address_line1", ""),
            "street": p.get("street", ""), "building_number": p.get("housenumber", ""),
            "village": p.get("suburb", ""), "district": p.get("district", ""),
            "city": p.get("city") or p.get("county", ""), "province": "Bali",
            "postcode": p.get("postcode", ""), "latitude": p["lat"], "longitude": p["lon"],
            "formatted": p.get("formatted", ""),
        })
    return jsonify(results=addresses, attribution="Powered by Geoapify | © OpenStreetMap contributors")


@bp.get("/admin")
@roles_required("admin")
def manage():
    return render_template("admin/locations.html", offices=Location.query.order_by(Location.name).all())


@bp.post("/admin")
@roles_required("admin")
def save_office():
    data = request.get_json(silent=True) or {}
    try:
        address = validate_address(data.get("address"), office_admin=True)
        if address["kind"] != "office":
            raise ValueError("Jenis lokasi harus kantor rental.")
        office = Location.query.filter_by(id=data["id"]).with_for_update().first() if data.get("id") else Location()
        if office is None:
            return jsonify(error="Kantor tidak ditemukan."), 404
        if office.id and data.get("version") != office.updated_at.isoformat():
            return jsonify(error="Data kantor berubah. Muat ulang sebelum menyimpan."), 409
        office.name = address["place_name"]
        if len(office.name) > 120:
            raise ValueError("Nama kantor maksimal 120 karakter.")
        office.address = address["formatted"]
        office.address_data = address
        office.is_active = data.get("active") is True
        office.verified_by_id = current_user.id
        db.session.add(office)
        db.session.commit()
        return jsonify(message="Alamat kantor berhasil disimpan.", id=office.id)
    except (ValueError, TypeError, IntegrityError):
        db.session.rollback()
        return jsonify(error="Gagal menyimpan. Periksa alamat Bali, konfirmasi pin, dan nama kantor yang unik."), 422
