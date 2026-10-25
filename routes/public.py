"""Route publik untuk beranda, katalog, detail, dan formulir pemesanan."""

from datetime import datetime
from decimal import Decimal
from secrets import token_hex
from urllib.parse import quote

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import false, or_

from extensions import db, limiter
from models import (
    Category,
    Driver,
    Location,
    RentalInquiry,
    Rental,
    Review,
    Vehicle,
    VehicleSpecification,
)
from services.availability_service import driver_is_available, vehicle_is_available
from utils.validators import decimal_amount, limited_text
from services.location_service import bookable_offices


bp = Blueprint("public", __name__)


# ==========================================================
# 01. FUNGSI BANTU FORMAT DAN PESAN WHATSAPP
# Bagian ini menghitung biaya dan menyusun ringkasan pesanan.
# ==========================================================
# Memformat nominal dengan awalan Rp dan pemisah ribuan Indonesia.
def format_rupiah(value):
    return f"Rp {Decimal(value):,.0f}".replace(",", ".")


def mask_identifier(value, visible=4):
    """Menyamarkan identitas agar tidak bocor melalui URL eksternal."""
    text = "".join(filter(str.isdigit, value or ""))
    if len(text) <= visible:
        return "*" * len(text)
    return f"{'*' * (len(text) - visible)}{text[-visible:]}"


def build_whatsapp_message(
    *,
    form,
    vehicle,
    driver,
    pickup_location,
    start_date,
    end_date,
    pickup_time,
    nik,
    detail_url,
):
    """Build a clear WhatsApp summary for the customer and administrator."""
    duration = (end_date - start_date).days + 1
    vehicle_cost = Decimal(vehicle.daily_price) * duration
    driver_cost = Decimal(driver.daily_rate) * duration if driver else Decimal("0")
    estimated_total = vehicle_cost + driver_cost + Decimal(vehicle.deposit)
    request_code = f"KG-WA-{datetime.now():%Y%m%d%H%M%S}-{token_hex(2).upper()}"

    sim_type = form.get("sim_type", "-")
    sim_number = form.get("sim_number", "").strip() or "-"
    driver_name = driver.name if driver else "Tanpa pengemudi"
    license_summary = (
        "Tidak diperlukan (dengan pengemudi)"
        if driver
        else f"{sim_type} / {mask_identifier(sim_number)}"
    )
    return (
        "*PENGAJUAN SEWA KENDARAGO*\n"
        f"Referensi: {request_code}\n\n"
        "Halo Admin KendaraGo,\n"
        "Saya ingin mengajukan sewa kendaraan dengan rincian berikut.\n\n"
        "*Data Penyewa*\n"
        f"Nama: {form['full_name'].strip()}\n"
        f"WhatsApp: {form['whatsapp'].strip()}\n"
        f"NIK (disamarkan): {mask_identifier(nik)}\n"
        f"SIM: {license_summary}\n"
        f"Kontak darurat: {form['emergency_phone'].strip()}\n\n"
        "*Kendaraan & Jadwal*\n"
        f"Kendaraan: {vehicle.name} ({vehicle.code})\n"
        f"Tanggal sewa: {start_date:%d/%m/%Y} s.d. {end_date:%d/%m/%Y}\n"
        f"Durasi: {duration} hari\n"
        f"Pengambilan: pukul {pickup_time:%H:%M} waktu setempat\n"
        f"Pengemudi: {driver_name}\n\n"
        "*Lokasi Pengambilan*\n"
        f"{pickup_location.name}\n"
        f"{pickup_location.address}\n"
        "Pengembalian di lokasi yang sama.\n\n"
        "*Rincian Estimasi Biaya*\n"
        f"Sewa: {format_rupiah(vehicle.daily_price)} x {duration} hari = {format_rupiah(vehicle_cost)}\n"
        f"Pengemudi: {format_rupiah(driver_cost)}\n"
        f"Deposit: {format_rupiah(vehicle.deposit)}\n"
        f"*Total estimasi: {format_rupiah(estimated_total)}*\n\n"
        "Pengajuan ini belum merupakan konfirmasi pemesanan. "
        "Ketersediaan kendaraan dan biaya akhir menunggu konfirmasi admin.\n\n"
        "Saya menyetujui syarat penyewaan dan kebijakan privasi KendaraGo.\n\n"
        "Mohon konfirmasi ketersediaan dan informasikan langkah pemesanan selanjutnya.\n"
        "Terima kasih."
    )


# ==========================================================
# 02. HALAMAN BERANDA DAN KATALOG
# Route publik untuk melihat serta mencari kendaraan.
# ==========================================================
# Mengambil data kendaraan dan informasi yang diperlukan beranda.
@bp.route("/")
def home():
    available_vehicles = Vehicle.query.filter_by(is_active=True, status="Tersedia")
    vehicles = available_vehicles.order_by(Vehicle.created_at.desc()).limit(9).all()
    categories = Category.query.filter_by(is_active=True).all()
    reviews = (
        Review.query.filter_by(is_visible=True)
        .order_by(Review.review_date.desc())
        .limit(3)
        .all()
    )
    return render_template(
        "public/home.html",
        vehicles=vehicles,
        vehicle_count=available_vehicles.count(),
        categories=categories,
        reviews=reviews,
    )


# Memfilter data kendaraan dan menampilkan daftar armada.
@bp.route("/kendaraan")
def vehicles():
    query = Vehicle.query.filter_by(is_active=True)
    keyword = request.args.get("q", "").strip()
    if keyword:
        query = query.filter(
            or_(Vehicle.name.ilike(f"%{keyword}%"), Vehicle.brand.ilike(f"%{keyword}%"))
        )
    for field, column in [
        ("category", Vehicle.category_id),
        ("transmission", Vehicle.transmission),
        ("fuel", Vehicle.fuel_type),
        ("location", Vehicle.location_id),
    ]:
        value = request.args.get(field)
        if value:
            query = query.filter(column == value)
    try:
        min_price = (
            decimal_amount(request.args["min_price"], "Harga minimum")
            if request.args.get("min_price")
            else None
        )
        max_price = (
            decimal_amount(request.args["max_price"], "Harga maksimum")
            if request.args.get("max_price")
            else None
        )
    except ValueError:
        abort(400)
    if min_price is not None:
        query = query.filter(Vehicle.daily_price >= min_price)
    if max_price is not None:
        query = query.filter(Vehicle.daily_price <= max_price)
    if min_price is not None and max_price is not None and min_price > max_price:
        query = query.filter(false())
    sort = request.args.get("sort", "newest")
    query = query.order_by(
        Vehicle.daily_price.asc()
        if sort == "cheapest"
        else (
            Vehicle.daily_price.desc()
            if sort == "highest"
            else Vehicle.created_at.desc()
        )
    )
    page = query.paginate(
        page=request.args.get("page", 1, type=int),
        per_page=current_app.config["ITEMS_PER_PAGE"],
        error_out=False,
    )
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    if start and end:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
            page.items = [
                v
                for v in page.items
                if vehicle_is_available(v.id, start_date, end_date)
            ]
        except ValueError:
            pass
    return render_template(
        "public/vehicles.html",
        page=page,
        categories=Category.query.filter_by(is_active=True).all(),
        locations=bookable_offices(),
    )


# Memfilter kendaraan touring dan menampilkan katalog spesifikasinya.
@bp.route("/motor-touring")
def touring_catalog():
    query = Vehicle.query.join(VehicleSpecification).filter(Vehicle.is_active.is_(True))
    keyword = request.args.get("q", "").strip()
    if keyword:
        query = query.filter(
            or_(Vehicle.name.ilike(f"%{keyword}%"), Vehicle.brand.ilike(f"%{keyword}%"))
        )
    if request.args.get("brand"):
        query = query.filter(Vehicle.brand == request.args["brand"])
    if request.args.get("touring_class"):
        query = query.filter(
            VehicleSpecification.vehicle_class == request.args["touring_class"]
        )
    if request.args.get("origin"):
        query = query.filter(
            VehicleSpecification.brand_origin == request.args["origin"]
        )
    if request.args.get("min_cc", type=int):
        query = query.filter(
            VehicleSpecification.displacement_cc >= request.args.get("min_cc", type=int)
        )
    if request.args.get("max_cc", type=int):
        query = query.filter(
            VehicleSpecification.displacement_cc <= request.args.get("max_cc", type=int)
        )
    sort = request.args.get("sort", "name")
    order = (
        Vehicle.daily_price.asc()
        if sort == "price_low"
        else (
            Vehicle.daily_price.desc()
            if sort == "price_high"
            else (
                VehicleSpecification.displacement_cc.desc()
                if sort == "cc_high"
                else Vehicle.name.asc()
            )
        )
    )
    page = query.order_by(order).paginate(
        page=request.args.get("page", 1, type=int), per_page=12, error_out=False
    )
    specs = VehicleSpecification.query.all()
    return render_template(
        "public/touring_catalog.html",
        page=page,
        brands=sorted({s.vehicle.brand for s in specs}),
        classes=sorted({s.vehicle_class for s in specs}),
        origins=sorted({s.brand_origin for s in specs if s.brand_origin}),
        total=VehicleSpecification.query.count(),
    )


# ==========================================================
# 03. DETAIL KENDARAAN
# Mengambil satu kendaraan aktif sebelum formulir sewa dibuka.
# ==========================================================
# Mengambil satu kendaraan untuk halaman detail publik.
@bp.route("/kendaraan/<int:vehicle_id>")
def vehicle_detail(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, is_active=True).first_or_404()
    return render_template("public/vehicle_detail.html", vehicle=vehicle)


# ==========================================================
# 04. FORMULIR PENYEWAAN RINGKAS
# Alur: muat pilihan, validasi data, cek ketersediaan, lalu buka WhatsApp.
# ==========================================================
# Memvalidasi formulir sewa publik dan menyusun permintaan melalui WhatsApp.
@bp.route("/kendaraan/<int:vehicle_id>/pesan", methods=["GET", "POST"])
@limiter.limit("5 per 10 minutes", methods=["POST"])
@limiter.limit("20 per day", methods=["POST"])
def rental_request(vehicle_id):
    from routes.booking_form import booking_form
    return booking_form(vehicle_id)


@bp.get('/pesanan')
def guest_orders():
    from routes.booking_form import guest_session_key
    from flask_login import current_user
    if current_user.is_authenticated and current_user.role == 'pelanggan':
        return redirect(url_for('customer.dashboard'))
    key = guest_session_key()
    rentals = Rental.query.filter_by(guest_session_key=key).order_by(Rental.id.desc()).all() if key else []
    return render_template('public/guest_orders.html', rentals=rentals)


@bp.get('/pesanan/<int:rental_id>')
def guest_detail(rental_id):
    from routes.booking_form import guest_session_key
    key = guest_session_key()
    if not key:
        abort(404)
    rental = Rental.query.filter_by(id=rental_id, guest_session_key=key).first_or_404()
    return render_template('public/guest_detail.html', rental=rental)


# ==========================================================
# 05. HALAMAN INFORMASI
# Konten statis: tentang, panduan menyewa, syarat, dan kontak.
# ==========================================================
# Menampilkan informasi tentang layanan KendaraGo.
@bp.route("/tentang")
def about():
    return render_template(
        "public/content.html",
        title="Tentang KendaraGo",
        content="KendaraGo membantu Anda menyewa mobil dan sepeda motor dengan proses transparan, cepat, dan aman.",
    )


# Menampilkan petunjuk penggunaan layanan penyewaan.
@bp.route("/cara-menyewa")
def how_to():
    return render_template(
        "public/content.html",
        title="Cara Menyewa",
        content="Pilih kendaraan, isi nama dan nomor kontak tanpa wajib login, tentukan jadwal serta titik temu, lalu kirim pesanan. Admin atau petugas memeriksa ketersediaan dan menyetujui pesanan. Pantau status melalui menu Pesanan; pembayaran dilakukan setelah pesanan disetujui.",
    )


# Menampilkan ketentuan layanan penyewaan.
@bp.route("/syarat")
def terms():
    return render_template(
        "public/content.html",
        title="Syarat dan Ketentuan",
        content="Penyewa wajib memiliki identitas dan SIM yang berlaku, menaati periode sewa, serta mengembalikan kendaraan dalam kondisi baik.",
    )


# Menampilkan informasi kebijakan privasi.
@bp.route("/privasi")
def privacy():
    return render_template(
        "public/content.html",
        title="Kebijakan Privasi",
        content=(
            "Data identitas digunakan hanya untuk verifikasi dan pelaksanaan sewa. "
            "Dokumen disimpan pada area privat, hanya dapat diperiksa oleh pemilik "
            "dan petugas berwenang, serta dapat diminta untuk diperbarui atau dihapus "
            "dengan menghubungi support@kendarago.com. NIK dan nomor SIM tidak dikirim "
            "secara lengkap melalui tautan WhatsApp."
        ),
    )


# Menampilkan informasi kontak layanan.
@bp.route("/kontak")
def contact():
    phone_number = current_app.config["WHATSAPP_DISPLAY_NUMBER"]
    content = f"Hubungi kami di support@kendarago.com atau {phone_number}."
    return render_template("public/content.html", title="Kontak", content=content)
