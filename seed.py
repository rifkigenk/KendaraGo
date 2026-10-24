# ==========================================================
# 01. DATA AWAL APLIKASI
# Membuat akun demo, armada, lokasi, promo, dan transaksi contoh dalam konteks Flask.
# ==========================================================

from datetime import date, time, timedelta
from decimal import Decimal

from app import create_app
from extensions import db
from models import (
    AppSetting,
    Category,
    CustomerProfile,
    Driver,
    Facility,
    Location,
    Promotion,
    Rental,
    RentalStatusLog,
    Review,
    User,
    Vehicle,
)


# Membuat akun demo dengan hash password serta profil jika perannya pelanggan.
def user(name, email, password, role, phone):
    item = User(name=name, email=email, role=role, phone=phone)
    item.set_password(password)
    if role == "pelanggan":
        item.profile = CustomerProfile(
            gender="Laki-laki",
            birth_date=date(1995, 5, 12),
            address="Jl. Merdeka No. 10, Denpasar, Bali",
            ktp_number="3174000000000001",
            sim_number="SIM-A-001",
            sim_type="SIM A",
            emergency_contact="081299999999",
            verification_status="Terverifikasi",
        )
    return item


# Mengisi data demo awal dan menjalankan pengayaan katalog yang diperlukan.
def seed():
    app = create_app()
    with app.app_context():
        db.create_all()
        if User.query.filter_by(email="admin@kendarago.com").first():
            from enrich_seed import enrich

            enrich()
            print("Data awal sudah tersedia; katalog tambahan dipastikan lengkap.")
            return

        admin = user(
            "Administrator KendaraGo",
            "admin@kendarago.com",
            "Admin123!",
            "admin",
            "081211110001",
        )
        staff = user(
            "Petugas KendaraGo",
            "petugas@kendarago.com",
            "Petugas123!",
            "petugas",
            "081211110002",
        )
        customer = user(
            "Pelanggan Demo",
            "pelanggan@kendarago.com",
            "Pelanggan123!",
            "pelanggan",
            "081211110003",
        )
        returning_customer = user(
            "Pelanggan Lama KendaraGo",
            "pelanggan.lama@kendarago.com",
            "PelangganLama123!",
            "pelanggan",
            "081211110004",
        )
        returning_customer.profile.ktp_number = "3174000000000002"
        db.session.add_all([admin, staff, customer, returning_customer])

        locations = [
            Location(
                name="Denpasar",
                address="Jl. By Pass Ngurah Rai, Kota Denpasar, Bali",
                phone="03615550101",
            ),
            Location(
                name="Kuta",
                address="Jl. Raya Kuta, Kabupaten Badung, Bali",
                phone="03615550102",
            ),
            Location(
                name="Ubud",
                address="Jl. Raya Ubud, Kabupaten Gianyar, Bali",
                phone="03615550103",
            ),
        ]
        categories = [
            Category(
                name="City Car",
                vehicle_type="Mobil",
                description="Ringkas dan hemat untuk dalam kota",
                late_fee_per_day=250000,
            ),
            Category(
                name="MPV Keluarga",
                vehicle_type="Mobil",
                description="Lapang untuk perjalanan keluarga",
                late_fee_per_day=350000,
            ),
            Category(
                name="Motor Matic",
                vehicle_type="Sepeda motor",
                description="Praktis untuk mobilitas harian",
                late_fee_per_day=100000,
            ),
            Category(
                name="Motor Sport",
                vehicle_type="Sepeda motor",
                description="Bertenaga untuk pengalaman berkendara",
                late_fee_per_day=175000,
            ),
        ]
        facilities = [
            Facility(name=name, icon=icon)
            for name, icon in [
                ("AC", "snow"),
                ("Bluetooth", "bluetooth"),
                ("Audio", "music-note"),
                ("GPS", "geo"),
                ("Helm", "shield"),
                ("Jas hujan", "cloud-rain"),
                ("Charger", "battery-charging"),
                ("Child seat", "person"),
                ("Kamera belakang", "camera-video"),
                ("Kotak P3K", "heart-pulse"),
            ]
        ]
        drivers = [
            Driver(
                name="Budi Santoso",
                phone="081300000101",
                license_number="DRV-A-101",
                address="Denpasar, Bali",
                daily_rate=250000,
            ),
            Driver(
                name="Andi Pratama",
                phone="081300000102",
                license_number="DRV-A-102",
                address="Kuta, Bali",
                daily_rate=275000,
            ),
            Driver(
                name="Rizky Hidayat",
                phone="081300000103",
                license_number="DRV-A-103",
                address="Ubud, Bali",
                daily_rate=250000,
            ),
        ]
        db.session.add_all(locations + categories + facilities + drivers)
        db.session.flush()

        specs = [
            (
                "CAR-001",
                0,
                "Toyota Agya GR",
                "Toyota",
                "Agya",
                "B 1001 KG",
                2024,
                "Putih",
                5,
                "Otomatis",
                "Bensin",
                350000,
            ),
            (
                "CAR-002",
                0,
                "Honda Brio Satya",
                "Honda",
                "Brio",
                "B 1002 KG",
                2023,
                "Kuning",
                5,
                "Manual",
                "Bensin",
                325000,
            ),
            (
                "CAR-003",
                1,
                "Toyota Avanza",
                "Toyota",
                "Avanza",
                "B 1003 KG",
                2024,
                "Hitam",
                7,
                "Otomatis",
                "Bensin",
                550000,
            ),
            (
                "CAR-004",
                1,
                "Mitsubishi Xpander",
                "Mitsubishi",
                "Xpander",
                "B 1004 KG",
                2024,
                "Abu-abu",
                7,
                "Otomatis",
                "Bensin",
                625000,
            ),
            (
                "CAR-005",
                1,
                "Toyota Innova Zenix",
                "Toyota",
                "Innova",
                "B 1005 KG",
                2025,
                "Putih",
                7,
                "Otomatis",
                "Hybrid",
                900000,
            ),
            (
                "MTR-001",
                2,
                "Honda Vario 160",
                "Honda",
                "Vario",
                "B 6001 KGO",
                2024,
                "Merah",
                2,
                "Otomatis",
                "Bensin",
                125000,
            ),
            (
                "MTR-002",
                2,
                "Yamaha NMAX",
                "Yamaha",
                "NMAX",
                "B 6002 KGO",
                2024,
                "Hitam",
                2,
                "Otomatis",
                "Bensin",
                175000,
            ),
            (
                "MTR-003",
                2,
                "Honda Scoopy",
                "Honda",
                "Scoopy",
                "B 6003 KGO",
                2023,
                "Krem",
                2,
                "Otomatis",
                "Bensin",
                110000,
            ),
            (
                "MTR-004",
                3,
                "Yamaha R15",
                "Yamaha",
                "R15",
                "B 6004 KGO",
                2023,
                "Biru",
                2,
                "Manual",
                "Bensin",
                250000,
            ),
            (
                "MTR-005",
                3,
                "Honda CBR 250RR",
                "Honda",
                "CBR",
                "B 6005 KGO",
                2024,
                "Merah",
                2,
                "Manual",
                "Bensin",
                350000,
            ),
        ]
        vehicles = []
        for index, spec in enumerate(specs):
            (
                code,
                category_idx,
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
            ) = spec
            vehicle = Vehicle(
                code=code,
                category=categories[category_idx],
                location=locations[index % 3],
                name=name,
                brand=brand,
                model=model,
                license_plate=plate,
                chassis_number=f"CHASSIS{index+1:04}",
                engine_number=f"ENGINE{index+1:04}",
                production_year=year,
                color=color,
                passenger_capacity=capacity,
                transmission=transmission,
                fuel_type=fuel,
                daily_price=price,
                deposit=Decimal(price) * 2,
                last_mileage=10000 + index * 1250,
                description=f"{name} terawat, bersih, dan siap menemani perjalanan Anda.",
                tax_date=date.today() + timedelta(days=90 + index * 15),
                registration_expiry=date.today() + timedelta(days=180 + index * 20),
            )
            vehicle.facilities = facilities[:4] + (
                facilities[7:10] if category_idx < 2 else facilities[4:7]
            )
            vehicles.append(vehicle)
        db.session.add_all(vehicles)

        promos = [
            Promotion(
                code="HEMAT10",
                name="Hemat 10%",
                description="Diskon pelanggan baru",
                discount_type="Persentase",
                discount_value=10,
                max_discount=150000,
                minimum_transaction=300000,
                start_date=date.today() - timedelta(days=30),
                end_date=date.today() + timedelta(days=365),
                quota=100,
            ),
            Promotion(
                code="LIBURAN50",
                name="Potongan Liburan",
                description="Potongan langsung Rp50.000",
                discount_type="Nominal",
                discount_value=50000,
                minimum_transaction=500000,
                start_date=date.today() - timedelta(days=30),
                end_date=date.today() + timedelta(days=180),
                quota=50,
            ),
        ]
        db.session.add_all(promos)
        db.session.flush()

        completed = Rental(
            booking_code="KG-DEMO-0001",
            customer=returning_customer,
            vehicle=vehicles[0],
            pickup_location=locations[0],
            return_location=locations[0],
            start_date=date.today() - timedelta(days=20),
            end_date=date.today() - timedelta(days=18),
            pickup_time=time(9, 0),
            duration_days=3,
            with_driver=False,
            daily_price=350000,
            vehicle_subtotal=1050000,
            driver_fee=0,
            additional_fee=0,
            discount=100000,
            deposit=700000,
            total_payment=1650000,
            status="Selesai",
        )
        db.session.add(completed)
        db.session.flush()
        db.session.add(
            RentalStatusLog(
                rental=completed,
                new_status="Selesai",
                changed_by_id=admin.id,
                notes="Transaksi contoh",
            )
        )
        db.session.add(
            Review(
                customer=customer,
                vehicle=vehicles[0],
                rental=completed,
                rating=5,
                comment="Kendaraan bersih dan prosesnya sangat mudah.",
            )
        )
        db.session.add_all(
            [
                AppSetting(
                    setting_key="company_name",
                    setting_value="KendaraGo",
                    description="Nama aplikasi",
                ),
                AppSetting(
                    setting_key="tagline",
                    setting_value="Sewa Kendaraan Mudah, Cepat, dan Aman.",
                    description="Tagline aplikasi",
                ),
            ]
        )
        db.session.commit()
        from enrich_seed import enrich

        enrich()
        print("Seed berhasil dibuat.")
        print("Admin: admin@kendarago.com / Admin123!")
        print("Petugas: petugas@kendarago.com / Petugas123!")
        print("Pelanggan: pelanggan@kendarago.com / Pelanggan123!")
        print("Pelanggan lama: pelanggan.lama@kendarago.com / PelangganLama123!")


if __name__ == "__main__":
    seed()
