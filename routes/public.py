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
from models import Category, Driver, Location, RentalInquiry, Review, Vehicle, VehicleSpecification
from services.availability_service import driver_is_available, vehicle_is_available
from utils.validators import decimal_amount, limited_text


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
        locations=Location.query.filter_by(is_active=True).all(),
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
    # 04A. Data yang diperlukan untuk menampilkan formulir.
    vehicle = Vehicle.query.filter_by(id=vehicle_id, is_active=True).first_or_404()
    locations = Location.query.filter_by(is_active=True).order_by(Location.name).all()
    drivers = Driver.query.filter_by(is_active=True).order_by(Driver.name).all()
    error = None

    if request.method == "POST":
        try:
            # 04B. Pastikan seluruh data inti telah diisi.
            required_fields = {
                "full_name": "nama lengkap",
                "nik": "NIK",
                "whatsapp": "nomor WhatsApp",
                "emergency_phone": "nomor kontak darurat",
                "start_date": "tanggal mulai",
                "end_date": "tanggal selesai",
                "pickup_time": "waktu pengambilan",
            }
            missing = [
                label
                for field, label in required_fields.items()
                if not request.form.get(field, "").strip()
            ]
            if missing:
                raise ValueError(f"Lengkapi bagian: {', '.join(missing)}.")

            # 04C. Bersihkan identitas dan periksa format kontak.
            full_name = limited_text(
                request.form["full_name"],
                "Nama lengkap",
                minimum=3,
                maximum=120,
                required=True,
            )

            nik = "".join(filter(str.isdigit, request.form["nik"]))
            if len(nik) != 16:
                raise ValueError("NIK harus terdiri dari 16 digit.")

            for field, label in (
                ("whatsapp", "Nomor WhatsApp"),
                ("emergency_phone", "Nomor kontak darurat"),
            ):
                phone_digits = "".join(filter(str.isdigit, request.form[field]))
                if not 9 <= len(phone_digits) <= 15:
                    raise ValueError(f"{label} harus terdiri dari 9 sampai 15 digit.")

            # 04D. Ubah jadwal menjadi objek tanggal dan cek ketersediaan unit.
            today = datetime.now().date()
            start_date = datetime.strptime(
                request.form["start_date"], "%Y-%m-%d"
            ).date()
            end_date = datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
            pickup_time = datetime.strptime(request.form["pickup_time"], "%H:%M").time()
            if start_date < today:
                raise ValueError("Tanggal mulai tidak boleh sebelum hari ini.")
            if end_date < start_date:
                raise ValueError("Tanggal selesai tidak boleh sebelum tanggal mulai.")
            if vehicle.status != "Tersedia" or not vehicle_is_available(
                vehicle.id, start_date, end_date
            ):
                raise ValueError(
                    "Kendaraan tidak tersedia pada periode tersebut. Silakan pilih tanggal lain."
                )

            # 04E. Pastikan lokasi pengambilan masih aktif.
            pickup_location_id = request.form.get("pickup_location_id", type=int)
            pickup_location = (
                db.session.get(Location, pickup_location_id)
                if pickup_location_id
                else None
            )
            if not pickup_location or not pickup_location.is_active:
                raise ValueError("Pilih lokasi pengambilan yang valid.")

            # 04F. Pengemudi dan SIM bersifat bergantian.
            with_driver = bool(request.form.get("with_driver"))
            driver = None
            if with_driver:
                driver_id = request.form.get("driver_id", type=int)
                driver = db.session.get(Driver, driver_id) if driver_id else None
                if not driver or not driver.is_active:
                    raise ValueError("Pilih pengemudi yang tersedia.")
                if not driver_is_available(driver.id, start_date, end_date):
                    raise ValueError(
                        "Pengemudi tersebut tidak tersedia pada periode yang dipilih."
                    )
            elif (
                not request.form.get("sim_type")
                or not request.form.get("sim_number", "").strip()
            ):
                raise ValueError(
                    "Jenis dan nomor SIM wajib diisi jika menyewa tanpa pengemudi."
                )
            elif (
                not 8
                <= len("".join(filter(str.isdigit, request.form["sim_number"])))
                <= 16
            ):
                raise ValueError("Nomor SIM harus terdiri dari 8 sampai 16 digit.")

            # 04G. Persetujuan pengguna wajib sebelum diarahkan ke WhatsApp.
            if not request.form.get("terms"):
                raise ValueError(
                    "Anda harus menyetujui syarat dan ketentuan penyewaan."
                )

            sanitized_form = request.form.to_dict()
            sanitized_form["full_name"] = full_name

            inquiry = RentalInquiry(
                vehicle_id=vehicle.id,
                driver_id=driver.id if driver else None,
                pickup_location_id=pickup_location.id,
                full_name=full_name,
                nik=nik,
                whatsapp="".join(filter(str.isdigit, request.form["whatsapp"])),
                emergency_phone="".join(filter(str.isdigit, request.form["emergency_phone"])),
                start_date=start_date,
                end_date=end_date,
                pickup_time=pickup_time,
                with_driver=with_driver,
                sim_type=None if with_driver else request.form.get("sim_type"),
                sim_number=None if with_driver else "".join(filter(str.isdigit, request.form["sim_number"])),
            )
            db.session.add(inquiry)
            db.session.commit()

            # 04H. Susun pesan final dan arahkan pengguna ke WhatsApp.
            detail_url = url_for(
                "public.vehicle_detail", vehicle_id=vehicle.id, _external=True
            )
            message = build_whatsapp_message(
                form=sanitized_form,
                vehicle=vehicle,
                driver=driver,
                pickup_location=pickup_location,
                start_date=start_date,
                end_date=end_date,
                pickup_time=pickup_time,
                nik=nik,
                detail_url=detail_url,
            )
            whatsapp_url = f"https://wa.me/{current_app.config['WHATSAPP_NUMBER']}?text={quote(message, safe='')}"
            # Render a same-origin response before navigating to WhatsApp.
            # Browsers may block external POST redirects under form-action 'self'.
            return render_template(
                "public/whatsapp_continue.html", whatsapp_url=whatsapp_url
            )
        except (TypeError, ValueError) as exception:
            error = str(exception)

    # Permintaan GET atau POST gagal akan kembali menampilkan formulir.
    return render_template(
        "public/rental_form.html",
        vehicle=vehicle,
        locations=locations,
        drivers=drivers,
        form=request.form,
        error=error,
    )


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
        content="Pilih kendaraan, isi formulir penyewaan lengkap tanpa login, lalu kirim pesan yang telah disiapkan melalui WhatsApp. Admin akan memeriksa ketersediaan, dokumen, dan mengonfirmasi pembayaran serta jadwal pengambilan.",
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
