# ==========================================================
# 01. ENRICH SEED
# Penambahan katalog dan transaksi demo. Aman dijalankan berulang kali.
# ==========================================================

"""Penambahan katalog dan transaksi demo. Aman dijalankan berulang kali."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from app import create_app
from extensions import db
from models import (
    Category,
    CustomerProfile,
    Facility,
    Location,
    Payment,
    Rental,
    RentalStatusLog,
    User,
    Vehicle,
)


INDONESIA_LOCATIONS = [
    ("Jakarta Pusat", "Jl. Medan Merdeka, Jakarta Pusat, DKI Jakarta", "089632358762"),
    ("Bandung Kota", "Jl. Asia Afrika, Kota Bandung, Jawa Barat", "089632358762"),
    (
        "Bandara Soekarno-Hatta",
        "Terminal 2, Bandara Soekarno-Hatta, Kota Tangerang, Banten",
        "089632358762",
    ),
    ("Banda Aceh", "Jl. Teuku Daud Beureueh, Banda Aceh, Aceh", "089632358762"),
    ("Medan", "Jl. Gatot Subroto, Kota Medan, Sumatera Utara", "089632358762"),
    ("Padang", "Jl. Khatib Sulaiman, Kota Padang, Sumatera Barat", "089632358762"),
    ("Pekanbaru", "Jl. Jenderal Sudirman, Kota Pekanbaru, Riau", "089632358762"),
    ("Batam", "Jl. Raja H. Fisabilillah, Kota Batam, Kepulauan Riau", "089632358762"),
    (
        "Palembang",
        "Jl. Demang Lebar Daun, Kota Palembang, Sumatera Selatan",
        "089632358762",
    ),
    ("Bandar Lampung", "Jl. Z.A. Pagar Alam, Bandar Lampung, Lampung", "089632358762"),
    ("Semarang", "Jl. Pandanaran, Kota Semarang, Jawa Tengah", "089632358762"),
    ("Yogyakarta", "Jl. Laksda Adisucipto, Sleman, DI Yogyakarta", "089632358762"),
    ("Surabaya", "Jl. Ahmad Yani, Kota Surabaya, Jawa Timur", "089632358762"),
    ("Malang", "Jl. Soekarno-Hatta, Kota Malang, Jawa Timur", "089632358762"),
    ("Denpasar", "Jl. By Pass Ngurah Rai, Kota Denpasar, Bali", "089632358762"),
    ("Mataram", "Jl. Pejanggik, Kota Mataram, Nusa Tenggara Barat", "089632358762"),
    ("Kupang", "Jl. Frans Seda, Kota Kupang, Nusa Tenggara Timur", "089632358762"),
    ("Pontianak", "Jl. Ahmad Yani, Kota Pontianak, Kalimantan Barat", "089632358762"),
    (
        "Banjarmasin",
        "Jl. Ahmad Yani, Kota Banjarmasin, Kalimantan Selatan",
        "089632358762",
    ),
    (
        "Balikpapan",
        "Jl. Jenderal Sudirman, Kota Balikpapan, Kalimantan Timur",
        "089632358762",
    ),
    (
        "Samarinda",
        "Jl. Pangeran Antasari, Kota Samarinda, Kalimantan Timur",
        "089632358762",
    ),
    ("Makassar", "Jl. A.P. Pettarani, Kota Makassar, Sulawesi Selatan", "089632358762"),
    ("Manado", "Jl. Sam Ratulangi, Kota Manado, Sulawesi Utara", "089632358762"),
    ("Palu", "Jl. Emy Saelan, Kota Palu, Sulawesi Tengah", "089632358762"),
    ("Kendari", "Jl. M.T. Haryono, Kota Kendari, Sulawesi Tenggara", "089632358762"),
    ("Ambon", "Jl. Jenderal Sudirman, Kota Ambon, Maluku", "089632358762"),
    ("Sorong", "Jl. Basuki Rahmat, Kota Sorong, Papua Barat Daya", "089632358762"),
    ("Jayapura", "Jl. Raya Abepura, Kota Jayapura, Papua", "089632358762"),
]


VEHICLE_LOCATION_BY_CODE = {
    "CAR-001": "Jakarta Pusat",
    "CAR-002": "Bandung Kota",
    "CAR-003": "Surabaya",
    "CAR-004": "Medan",
    "CAR-005": "Denpasar",
    "CAR-006": "Semarang",
    "CAR-007": "Makassar",
    "CAR-008": "Palembang",
    "CAR-009": "Banjarmasin",
    "CAR-010": "Padang",
    "CAR-011": "Pekanbaru",
    "MPV-001": "Yogyakarta",
    "EV-001": "Jakarta Pusat",
    "EV-002": "Surabaya",
    "SUV-001": "Bandung Kota",
    "SUV-002": "Medan",
    "SUV-003": "Makassar",
    "SUV-004": "Balikpapan",
    "SUV-005": "Samarinda",
    "SUV-006": "Bandar Lampung",
    "SUV-007": "Batam",
    "COM-001": "Palu",
    "COM-002": "Kendari",
    "COM-003": "Kupang",
    "COM-004": "Pontianak",
    "COM-005": "Banda Aceh",
    "COM-006": "Ambon",
    "MTR-001": "Jakarta Pusat",
    "MTR-002": "Bandung Kota",
    "MTR-003": "Yogyakarta",
    "MTR-004": "Surabaya",
    "MTR-005": "Denpasar",
    "MTR-006": "Malang",
    "MTR-007": "Mataram",
    "MTR-008": "Medan",
    "MTR-009": "Padang",
    "MTR-010": "Pekanbaru",
    "MTR-011": "Palembang",
    "MTR-012": "Banjarmasin",
    "MTR-013": "Manado",
    "MTR-014": "Sorong",
    "MTR-015": "Jayapura",
    "MTR-016": "Makassar",
}


CURRENT_MODEL_UPDATES = {
    "CAR-001": ("Toyota Agya GR Sport", "Agya GR Sport", 2026),
    "CAR-002": ("Honda Brio S CVT", "Brio", 2026),
    "CAR-003": ("All New Toyota Avanza 1.5 G CVT", "Avanza", 2026),
    "CAR-004": ("New Mitsubishi Xpander Exceed Tourer", "Xpander", 2026),
    "CAR-005": ("New Kijang Innova Zenix Hybrid EV", "Innova Zenix", 2026),
    "MTR-001": ("New Honda Vario 160 RoadSync", "Vario 160", 2026),
    "MTR-002": ("Yamaha NMAX Turbo", "NMAX", 2026),
    "MTR-003": ("New Honda Scoopy", "Scoopy", 2026),
}


BASE_VEHICLE_CODES = [
    "CAR-001",
    "CAR-002",
    "CAR-003",
    "CAR-004",
    "CAR-005",
    "MTR-001",
    "MTR-002",
    "MTR-003",
    "MTR-004",
    "MTR-005",
]


# Menentukan lokasi gambar katalog untuk kode kendaraan.
def catalog_image_path(code):
    return f"vehicles/catalog/{code.lower()}.jpg"


NEW_VEHICLES = [
    (
        "CAR-006",
        "City Car",
        "Daihatsu Ayla ADS",
        "Daihatsu",
        "Ayla",
        "B 1106 KGO",
        2025,
        "Putih",
        5,
        "Otomatis",
        "Bensin",
        340000,
        "vehicles/city-car-white.png",
    ),
    (
        "CAR-007",
        "City Car",
        "Suzuki Baleno Hatchback",
        "Suzuki",
        "Baleno",
        "B 1107 KGO",
        2024,
        "Putih",
        5,
        "Otomatis",
        "Bensin",
        430000,
        "vehicles/city-car-white.png",
    ),
    (
        "CAR-008",
        "MPV Keluarga",
        "Hyundai Stargazer",
        "Hyundai",
        "Stargazer",
        "B 1108 KGO",
        2025,
        "Abu-abu",
        7,
        "Otomatis",
        "Bensin",
        650000,
        "vehicles/family-mpv-gray.png",
    ),
    (
        "CAR-009",
        "MPV Keluarga",
        "Suzuki Ertiga Hybrid",
        "Suzuki",
        "Ertiga",
        "B 1109 KGO",
        2025,
        "Abu-abu",
        7,
        "Otomatis",
        "Hybrid",
        625000,
        "vehicles/family-mpv-gray.png",
    ),
    (
        "SUV-001",
        "SUV",
        "Honda BR-V Prestige",
        "Honda",
        "BR-V",
        "B 2101 KGO",
        2025,
        "Biru tua",
        7,
        "Otomatis",
        "Bensin",
        700000,
        "vehicles/suv-navy.png",
    ),
    (
        "SUV-002",
        "SUV",
        "Hyundai Creta Prime",
        "Hyundai",
        "Creta",
        "B 2102 KGO",
        2025,
        "Biru tua",
        5,
        "Otomatis",
        "Bensin",
        725000,
        "vehicles/suv-navy.png",
    ),
    (
        "SUV-003",
        "SUV",
        "Wuling Alvez EX",
        "Wuling",
        "Alvez",
        "B 2103 KGO",
        2024,
        "Merah",
        5,
        "Otomatis",
        "Bensin",
        575000,
        "vehicles/compact-suv-red-v2.webp",
    ),
    (
        "SED-001",
        "Sedan Premium",
        "BMW 320i Sport",
        "BMW",
        "320i",
        "B 3101 KGO",
        2025,
        "Hitam",
        5,
        "Otomatis",
        "Bensin",
        1650000,
        "vehicles/executive-sedan-black.png",
    ),
    (
        "SED-002",
        "Sedan Premium",
        "BYD Seal Performance",
        "BYD",
        "Seal",
        "B 3102 KGO",
        2025,
        "Perak",
        5,
        "Otomatis",
        "Listrik",
        1400000,
        "vehicles/electric-sedan-silver.png",
    ),
    (
        "COM-001",
        "Komersial",
        "Toyota Hilux Double Cabin",
        "Toyota",
        "Hilux",
        "B 4101 KGO",
        2024,
        "Putih",
        5,
        "Manual",
        "Diesel",
        1100000,
        "vehicles/pickup-white.png",
    ),
    (
        "COM-002",
        "Komersial",
        "Mitsubishi Triton HDX",
        "Mitsubishi",
        "Triton",
        "B 4102 KGO",
        2024,
        "Putih",
        5,
        "Manual",
        "Diesel",
        1050000,
        "vehicles/pickup-white.png",
    ),
    (
        "COM-003",
        "Komersial",
        "Toyota Hiace Premio",
        "Toyota",
        "Hiace",
        "B 4103 KGO",
        2025,
        "Putih",
        12,
        "Manual",
        "Diesel",
        1800000,
        "vehicles/minibus-white.png",
    ),
    (
        "MTR-006",
        "Motor Matic",
        "Honda Stylo 160",
        "Honda",
        "Stylo",
        "B 6106 KGO",
        2025,
        "Krem",
        2,
        "Otomatis",
        "Bensin",
        160000,
        "vehicles/retro-scooter-cream.png",
    ),
    (
        "MTR-007",
        "Motor Touring",
        "Kawasaki Versys-X 250",
        "Kawasaki",
        "Versys-X",
        "B 6107 KGO",
        2024,
        "Biru",
        2,
        "Manual",
        "Bensin",
        425000,
        "vehicles/rally-adventure-blue-v2.webp",
    ),
    (
        "CAR-010",
        "MPV Keluarga",
        "New Toyota Calya 1.2 G A/T",
        "Toyota",
        "Calya",
        "BA 1210 KGO",
        2026,
        "Putih",
        7,
        "Otomatis",
        "Bensin",
        475000,
        "vehicles/family-mpv-gray.png",
    ),
    (
        "CAR-011",
        "MPV Keluarga",
        "New Daihatsu Sigra 1.2 R A/T",
        "Daihatsu",
        "Sigra",
        "BM 1211 KGO",
        2026,
        "Merah",
        7,
        "Otomatis",
        "Bensin",
        450000,
        "vehicles/family-mpv-graphite-v2.webp",
    ),
    (
        "MPV-001",
        "MPV Keluarga",
        "New Toyota Veloz Hybrid EV Q CVT",
        "Toyota",
        "Veloz Hybrid",
        "AB 1301 KGO",
        2026,
        "Putih",
        7,
        "Otomatis",
        "Hybrid",
        725000,
        "vehicles/premium-hybrid-mpv-white-v2.webp",
    ),
    (
        "EV-001",
        "City Car",
        "BYD Atto 1 Premium",
        "BYD",
        "Atto 1",
        "B 1401 KGO",
        2026,
        "Kuning",
        5,
        "Otomatis",
        "Listrik",
        575000,
        "vehicles/electric-sedan-silver.png",
    ),
    (
        "EV-002",
        "MPV Keluarga",
        "BYD M6 Superior 7 Seater",
        "BYD",
        "M6",
        "L 1402 KGO",
        2026,
        "Perak",
        7,
        "Otomatis",
        "Listrik",
        850000,
        "vehicles/electric-sedan-silver.png",
    ),
    (
        "SUV-004",
        "SUV",
        "Toyota Rush GR Sport",
        "Toyota",
        "Rush",
        "KT 2204 KGO",
        2026,
        "Hitam",
        7,
        "Otomatis",
        "Bensin",
        675000,
        "vehicles/suv-navy.png",
    ),
    (
        "SUV-005",
        "SUV",
        "New Daihatsu Terios R ADS",
        "Daihatsu",
        "Terios",
        "KT 2205 KGO",
        2026,
        "Merah",
        7,
        "Otomatis",
        "Bensin",
        625000,
        "vehicles/compact-suv-red-v2.webp",
    ),
    (
        "SUV-006",
        "SUV",
        "New Honda WR-V RS Honda Sensing",
        "Honda",
        "WR-V",
        "BE 2206 KGO",
        2026,
        "Putih",
        5,
        "Otomatis",
        "Bensin",
        650000,
        "vehicles/compact-suv-red-v2.webp",
    ),
    (
        "SUV-007",
        "SUV",
        "Suzuki Fronx SGX Hybrid Kuro",
        "Suzuki",
        "Fronx",
        "BP 2207 KGO",
        2026,
        "Hitam",
        5,
        "Otomatis",
        "Hybrid",
        675000,
        "vehicles/suv-navy.png",
    ),
    (
        "COM-004",
        "Komersial",
        "Daihatsu Gran Max Pick Up 1.5",
        "Daihatsu",
        "Gran Max",
        "KB 4204 KGO",
        2026,
        "Putih",
        3,
        "Manual",
        "Bensin",
        575000,
        "vehicles/pickup-white.png",
    ),
    (
        "COM-005",
        "Komersial",
        "Suzuki New Carry Pick-Up",
        "Suzuki",
        "Carry",
        "BL 4205 KGO",
        2026,
        "Putih",
        3,
        "Manual",
        "Bensin",
        550000,
        "vehicles/pickup-white.png",
    ),
    (
        "COM-006",
        "Komersial",
        "Mitsubishi Colt L300 Euro 4",
        "Mitsubishi",
        "Colt L300",
        "DE 4206 KGO",
        2026,
        "Hitam",
        3,
        "Manual",
        "Diesel",
        650000,
        "vehicles/pickup-white.png",
    ),
    (
        "MTR-008",
        "Motor Matic",
        "Honda BeAT Deluxe Smart Key",
        "Honda",
        "BeAT",
        "BK 6208 KGO",
        2026,
        "Hitam",
        2,
        "Otomatis",
        "Bensin",
        100000,
        "vehicles/scooter-red.png",
    ),
    (
        "MTR-009",
        "Motor Matic",
        "Honda Vario 125 CBS ISS",
        "Honda",
        "Vario 125",
        "BA 6209 KGO",
        2026,
        "Merah",
        2,
        "Otomatis",
        "Bensin",
        120000,
        "vehicles/scooter-red.png",
    ),
    (
        "MTR-010",
        "Motor Matic",
        "Honda PCX 160 RoadSync",
        "Honda",
        "PCX 160",
        "BM 6210 KGO",
        2026,
        "Hitam",
        2,
        "Otomatis",
        "Bensin",
        185000,
        "vehicles/maxi-scooter-black.png",
    ),
    (
        "MTR-011",
        "Motor Matic",
        "Honda ADV 160 RoadSync",
        "Honda",
        "ADV 160",
        "BG 6211 KGO",
        2026,
        "Merah",
        2,
        "Otomatis",
        "Bensin",
        200000,
        "vehicles/adventure-bike-green.png",
    ),
    (
        "MTR-012",
        "Motor Matic",
        "Yamaha Aerox Alpha Turbo",
        "Yamaha",
        "Aerox Alpha",
        "DA 6212 KGO",
        2026,
        "Biru",
        2,
        "Otomatis",
        "Bensin",
        190000,
        "vehicles/maxi-scooter-black.png",
    ),
    (
        "MTR-013",
        "Motor Matic",
        "Yamaha Fazzio Hybrid Connected",
        "Yamaha",
        "Fazzio",
        "DB 6213 KGO",
        2026,
        "Krem",
        2,
        "Otomatis",
        "Bensin",
        130000,
        "vehicles/retro-scooter-cream.png",
    ),
    (
        "MTR-014",
        "Motor Matic",
        "Yamaha Gear Ultima Hybrid",
        "Yamaha",
        "Gear Ultima",
        "PB 6214 KGO",
        2026,
        "Merah",
        2,
        "Otomatis",
        "Bensin",
        115000,
        "vehicles/scooter-red.png",
    ),
    (
        "MTR-015",
        "Motor Matic",
        "Yamaha FreeGo 125 Connected",
        "Yamaha",
        "FreeGo 125",
        "PA 6215 KGO",
        2026,
        "Biru",
        2,
        "Otomatis",
        "Bensin",
        125000,
        "vehicles/maxi-scooter-black.png",
    ),
    (
        "MTR-016",
        "Motor Matic",
        "Suzuki Access 125",
        "Suzuki",
        "Access 125",
        "DD 6216 KGO",
        2026,
        "Putih",
        2,
        "Otomatis",
        "Bensin",
        120000,
        "vehicles/retro-scooter-cream.png",
    ),
]


# Armada premium global tetap disimpan untuk kebutuhan data/admin, tetapi tidak
# ditampilkan di katalog publik. Katalog utama difokuskan pada kendaraan harian
# kelas menengah yang lebih relevan bagi penyewa lokal.
HIDDEN_PREMIUM_PREFIXES = ("SED-", "TOUR-")
MAX_PUBLIC_DAILY_PRICE = Decimal("900000")

FACILITY_SPECS = {
    "AC": "snow",
    "Bluetooth": "bluetooth",
    "Audio": "music-note",
    "GPS": "geo",
    "USB charger": "usb-plug",
    "Airbag": "shield-check",
    "ABS": "disc",
    "Kamera belakang": "camera-video",
    "Sensor parkir": "broadcast-pin",
    "Kotak P3K": "heart-pulse",
    "Child seat opsional": "person",
    "Helm SNI (2)": "shield-check",
    "Jas hujan": "cloud-rain",
    "Phone holder": "phone",
    "Kunci pengaman": "lock",
    "Bagasi": "box-seam",
}

CAR_FACILITIES = [
    "AC",
    "Bluetooth",
    "Audio",
    "GPS",
    "USB charger",
    "Airbag",
    "ABS",
    "Kamera belakang",
    "Sensor parkir",
    "Kotak P3K",
]

COMMERCIAL_FACILITIES = [
    "AC",
    "Bluetooth",
    "Audio",
    "USB charger",
    "Kotak P3K",
]

MOTOR_FACILITIES = [
    "Helm SNI (2)",
    "Jas hujan",
    "USB charger",
    "Phone holder",
    "Kunci pengaman",
    "Kotak P3K",
]


def ensure_facilities():
    """Return a complete facility map without duplicating existing rows."""
    facilities = {facility.name: facility for facility in Facility.query.all()}
    for name, icon in FACILITY_SPECS.items():
        facility = facilities.get(name)
        if not facility:
            facility = Facility(name=name, icon=icon)
            db.session.add(facility)
            facilities[name] = facility
        else:
            facility.icon = icon
    db.session.flush()
    return facilities


# Memilih fasilitas kendaraan berdasarkan jenis dan kategori.
def facilities_for(vehicle, facilities):
    if vehicle.category.name == "Komersial":
        names = COMMERCIAL_FACILITIES
    elif vehicle.category.vehicle_type == "Mobil":
        names = CAR_FACILITIES
    else:
        names = MOTOR_FACILITIES
        if vehicle.category.name == "Motor Matic":
            names = [*names, "Bagasi"]
    if vehicle.category.name == "MPV Keluarga":
        names = [*names, "Child seat opsional"]
    return [facilities[name] for name in names]


def apply_public_catalog_policy():
    """Keep the public catalog moderate and reject cross-model photo reuse."""
    all_vehicles = Vehicle.query.all()
    for vehicle in all_vehicles:
        vehicle.is_active = (
            not vehicle.code.startswith(HIDDEN_PREMIUM_PREFIXES)
            and vehicle.daily_price <= MAX_PUBLIC_DAILY_PRICE
        )

    visible_categories = {
        vehicle.category_id for vehicle in all_vehicles if vehicle.is_active
    }
    for category in Category.query.all():
        category.is_active = category.id in visible_categories

    image_owners = {}
    for vehicle in (item for item in all_vehicles if item.is_active):
        if not vehicle.main_image:
            raise RuntimeError(f"Foto utama {vehicle.code} belum tersedia.")
        model_key = (
            vehicle.brand.casefold(),
            (vehicle.model or vehicle.name).casefold(),
        )
        owner = image_owners.get(vehicle.main_image)
        if owner and owner[1] != model_key:
            raise RuntimeError(
                f"Foto {vehicle.main_image} dipakai oleh model berbeda: "
                f"{owner[0]} dan {vehicle.code}."
            )
        image_owners[vehicle.main_image] = (vehicle.code, model_key)


# Memastikan lokasi cabang yang diperlukan katalog tersedia.
def ensure_locations():
    locations = {}
    for name, address, phone in INDONESIA_LOCATIONS:
        location = Location.query.filter_by(name=name).first()
        if not location:
            location = Location(name=name)
            db.session.add(location)
        location.address = address
        location.phone = phone
        location.is_active = True
        locations[name] = location
    db.session.flush()
    return locations


# Mengambil kategori yang ada atau membuat kategori baru.
def ensure_category(name, vehicle_type, fee):
    category = Category.query.filter_by(name=name).first()
    if not category:
        category = Category(
            name=name,
            vehicle_type=vehicle_type,
            late_fee_per_day=fee,
            description=f"Pilihan kendaraan kelas {name} yang terawat dan siap disewa.",
        )
        db.session.add(category)
        db.session.flush()
    return category


# Mengambil pelanggan demo berdasarkan email atau membuat akun dan profilnya.
def ensure_customer(index, name, email):
    customer = User.query.filter_by(email=email).first()
    if customer:
        return customer
    customer = User(
        name=name, email=email, phone=f"0812888800{index:02}", role="pelanggan"
    )
    customer.set_password("Pelanggan123!")
    customer.profile = CustomerProfile(
        address=f"Jl. Pelanggan KendaraGo No. {index}, Jakarta",
        ktp_number=f"3174000000001{index:03}",
        sim_number=f"SIM-DEMO-{index:03}",
        sim_type="SIM A",
        verification_status="Terverifikasi",
        emergency_contact=f"0812777700{index:02}",
    )
    db.session.add(customer)
    db.session.flush()
    return customer


def ensure_returning_customer():
    """Menyiapkan akun pelanggan lama dengan satu riwayat sewa selesai."""
    email = "pelanggan.lama@kendarago.com"
    customer = User.query.filter_by(email=email).first()
    if not customer:
        customer = User(
            name="Pelanggan Lama KendaraGo",
            email=email,
            phone="081211110004",
            role="pelanggan",
        )
        customer.set_password("PelangganLama123!")
        customer.profile = CustomerProfile(
            address="Jl. Pelanggan KendaraGo No. 4, Jakarta",
            ktp_number="3174000000000002",
            sim_number="SIM-LAMA-004",
            sim_type="SIM A",
            verification_status="Terverifikasi",
            emergency_contact="081277770004",
        )
        db.session.add(customer)
        db.session.flush()
    if not Rental.query.filter_by(customer_id=customer.id, status="Selesai").first():
        previous = Rental.query.filter_by(booking_code="KG-DEMO-0001").first()
        if previous:
            previous.customer_id = customer.id
        else:
            vehicle = Vehicle.query.filter_by(is_active=True).first()
            location = Location.query.filter_by(is_active=True).first()
            if vehicle and location:
                db.session.add(
                    Rental(
                        booking_code="KG-LOYAL-0001",
                        customer_id=customer.id,
                        vehicle_id=vehicle.id,
                        pickup_location_id=location.id,
                        return_location_id=location.id,
                        start_date=date.today() - timedelta(days=20),
                        end_date=date.today() - timedelta(days=18),
                        pickup_time=time(9, 0),
                        duration_days=3,
                        daily_price=vehicle.daily_price,
                        vehicle_subtotal=Decimal(vehicle.daily_price) * 3,
                        driver_fee=0,
                        additional_fee=0,
                        discount=0,
                        deposit=vehicle.deposit,
                        total_payment=Decimal(vehicle.daily_price) * 3 + Decimal(vehicle.deposit),
                        status="Selesai",
                    )
                )
    return customer


def seed_indonesia_catalog():
    """Create or refresh Indonesian locations and locally relevant vehicles."""
    locations = ensure_locations()

    category_specs = [
        ("City Car", "Mobil", 250000),
        ("MPV Keluarga", "Mobil", 350000),
        ("SUV", "Mobil", 450000),
        ("Sedan Premium", "Mobil", 750000),
        ("Komersial", "Mobil", 600000),
        ("Motor Matic", "Sepeda motor", 100000),
        ("Motor Sport", "Sepeda motor", 175000),
        ("Motor Touring", "Sepeda motor", 250000),
    ]
    for name, vehicle_type, fee in category_specs:
        ensure_category(name, vehicle_type, fee)
    facilities = ensure_facilities()

    for code in BASE_VEHICLE_CODES:
        vehicle = Vehicle.query.filter_by(code=code).first()
        if not vehicle:
            continue
        vehicle.main_image = catalog_image_path(code)
        vehicle.location = locations[
            VEHICLE_LOCATION_BY_CODE.get(code, "Jakarta Pusat")
        ]
        vehicle.is_active = True
        if code in CURRENT_MODEL_UPDATES:
            vehicle.name, vehicle.model, vehicle.production_year = (
                CURRENT_MODEL_UPDATES[code]
            )
        vehicle.facilities = facilities_for(vehicle, facilities)

    for index, spec in enumerate(NEW_VEHICLES, start=20):
        (
            code,
            category_name,
            name,
            brand,
            model,
            plate,
            year,
            color,
            capacity,
            transmission,
            fuel,
            price,
            _legacy_image,
        ) = spec
        image = catalog_image_path(code)
        existing_vehicle = Vehicle.query.filter_by(code=code).first()
        if existing_vehicle:
            existing_vehicle.category = Category.query.filter_by(
                name=category_name
            ).one()
            existing_vehicle.name = name
            existing_vehicle.brand = brand
            existing_vehicle.model = model
            existing_vehicle.production_year = year
            existing_vehicle.color = color
            existing_vehicle.passenger_capacity = capacity
            existing_vehicle.transmission = transmission
            existing_vehicle.fuel_type = fuel
            existing_vehicle.daily_price = price
            existing_vehicle.deposit = Decimal(price) * 2
            existing_vehicle.main_image = image
            existing_vehicle.location = locations[
                VEHICLE_LOCATION_BY_CODE.get(code, "Jakarta Pusat")
            ]
            existing_vehicle.is_active = (
                not code.startswith(HIDDEN_PREMIUM_PREFIXES)
                and Decimal(price) <= MAX_PUBLIC_DAILY_PRICE
            )
            existing_vehicle.facilities = facilities_for(existing_vehicle, facilities)
            continue
        vehicle = Vehicle(
            code=code,
            category=Category.query.filter_by(name=category_name).one(),
            location=locations[VEHICLE_LOCATION_BY_CODE.get(code, "Jakarta Pusat")],
            name=name,
            brand=brand,
            model=model,
            license_plate=plate,
            chassis_number=f"CHASSIS-NEW-{index}",
            engine_number=f"ENGINE-NEW-{index}",
            production_year=year,
            color=color,
            passenger_capacity=capacity,
            transmission=transmission,
            fuel_type=fuel,
            daily_price=price,
            deposit=Decimal(price) * 2,
            last_mileage=2500 + index * 310,
            description=f"{name} unit terbaru, rutin diservis, bersih, dan siap untuk perjalanan Anda.",
            main_image=image,
            status="Tersedia",
            tax_date=date.today() + timedelta(days=120 + index),
            registration_expiry=date.today() + timedelta(days=280 + index),
        )
        vehicle.is_active = (
            not code.startswith(HIDDEN_PREMIUM_PREFIXES)
            and Decimal(price) <= MAX_PUBLIC_DAILY_PRICE
        )
        vehicle.facilities = facilities_for(vehicle, facilities)
        db.session.add(vehicle)
    db.session.flush()
    return locations["Jakarta Pusat"]


# Menambahkan katalog dan transaksi demo setelah akun admin tersedia.
def enrich():
    if not User.query.filter_by(role="admin").first():
        raise RuntimeError("Jalankan seed.py terlebih dahulu.")

    location = seed_indonesia_catalog()
    ensure_returning_customer()

    customers = [
        ensure_customer(1, "Siti Rahmawati", "siti@demo.kendarago.com"),
        ensure_customer(2, "Dimas Saputra", "dimas@demo.kendarago.com"),
        ensure_customer(3, "Nadia Putri", "nadia@demo.kendarago.com"),
        ensure_customer(4, "Fajar Nugroho", "fajar@demo.kendarago.com"),
    ]
    admin = User.query.filter_by(role="admin").first()
    rental_specs = [
        (
            "KG-PAY-1001",
            customers[0],
            "CAR-003",
            -45,
            -42,
            "Selesai",
            "Transfer bank",
            "Diverifikasi",
        ),
        (
            "KG-PAY-1002",
            customers[1],
            "MTR-002",
            -30,
            -27,
            "Selesai",
            "QRIS",
            "Diverifikasi",
        ),
        (
            "KG-PAY-1003",
            customers[2],
            "SUV-001",
            -14,
            -11,
            "Selesai",
            "Transfer bank",
            "Diverifikasi",
        ),
        (
            "KG-PAY-1004",
            customers[3],
            "SED-002",
            -8,
            -6,
            "Selesai",
            "QRIS",
            "Diverifikasi",
        ),
        (
            "KG-PAY-1005",
            customers[0],
            "CAR-008",
            8,
            10,
            "Menunggu verifikasi pembayaran",
            "Transfer bank",
            "Menunggu",
        ),
        (
            "KG-PAY-1006",
            customers[1],
            "MTR-007",
            13,
            16,
            "Dikonfirmasi",
            "QRIS",
            "Diverifikasi",
        ),
        (
            "KG-PAY-1007",
            customers[2],
            "COM-003",
            20,
            22,
            "Menunggu pembayaran",
            None,
            None,
        ),
        (
            "KG-PAY-1008",
            customers[3],
            "SUV-003",
            27,
            30,
            "Menunggu pembayaran",
            "Transfer bank",
            "Ditolak",
        ),
    ]
    for sequence, (
        code,
        customer,
        vehicle_code,
        start_offset,
        end_offset,
        status,
        method,
        payment_status,
    ) in enumerate(rental_specs, 1):
        if Rental.query.filter_by(booking_code=code).first():
            continue
        vehicle = Vehicle.query.filter_by(code=vehicle_code).one()
        start_date, end_date = date.today() + timedelta(
            days=start_offset
        ), date.today() + timedelta(days=end_offset)
        days = (end_date - start_date).days + 1
        subtotal = Decimal(vehicle.daily_price) * days
        total = subtotal + Decimal(vehicle.deposit)
        rental = Rental(
            booking_code=code,
            customer_id=customer.id,
            vehicle_id=vehicle.id,
            pickup_location_id=location.id,
            return_location_id=location.id,
            start_date=start_date,
            end_date=end_date,
            pickup_time=time(9, 0),
            duration_days=days,
            with_driver=False,
            daily_price=vehicle.daily_price,
            vehicle_subtotal=subtotal,
            driver_fee=0,
            additional_fee=0,
            discount=0,
            deposit=vehicle.deposit,
            total_payment=total,
            status=status,
            customer_notes="Transaksi demo untuk menampilkan aktivitas pembayaran.",
        )
        db.session.add(rental)
        db.session.flush()
        db.session.add(
            RentalStatusLog(
                rental_id=rental.id,
                new_status=status,
                changed_by_id=admin.id,
                notes="Data demo lengkap",
            )
        )
        if method:
            payment = Payment(
                payment_number=f"PAY-DEMO-{sequence:04}",
                rental_id=rental.id,
                payment_date=datetime.now() - timedelta(days=max(0, -start_offset - 1)),
                method=method,
                account_holder=customer.name,
                amount=total,
                verification_status=payment_status,
                verified_by_id=admin.id if payment_status != "Menunggu" else None,
                verified_at=datetime.now() if payment_status != "Menunggu" else None,
                admin_notes=(
                    "Pembayaran contoh KendaraGo"
                    if payment_status != "Menunggu"
                    else None
                ),
            )
            db.session.add(payment)
    db.session.commit()
    from global_touring_seed import seed_touring

    seed_touring()
    apply_public_catalog_policy()
    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        enrich()
        print("Katalog dan pembayaran demo berhasil diperkaya.")
