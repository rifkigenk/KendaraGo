# ==========================================================
# 01. EKSPOR MODEL ENTITIES
# Menyediakan alias model dari entities agar impor melalui modul ini tetap kompatibel.
# ==========================================================

"""Model SQLAlchemy yang memetakan objek Python ke tabel database KendaraGo."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import current_app, has_app_context
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


def now():
    """Menghasilkan waktu UTC tanpa timezone agar cocok dengan kolom MySQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def default_payment_due_at():
    """Deadline bawaan untuk seed dan pembuatan objek di luar service rental."""
    hours = (
        current_app.config.get("PAYMENT_DEADLINE_HOURS", 2) if has_app_context() else 2
    )
    return now() + timedelta(hours=hours)


class TimestampMixin:
    """Menambahkan waktu dibuat dan diperbarui pada setiap model turunannya."""

    created_at = db.Column(db.DateTime, default=now, nullable=False)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now, nullable=False)


# Tabel penghubung untuk relasi many-to-many kendaraan dan fasilitas.
vehicle_facilities = db.Table(
    "vehicle_facilities",
    db.Column(
        "vehicle_id",
        db.Integer,
        db.ForeignKey("vehicles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "facility_id",
        db.Integer,
        db.ForeignKey("facilities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(UserMixin, TimestampMixin, db.Model):
    """Akun login untuk pelanggan, petugas, dan admin."""

    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="pelanggan", index=True)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    profile = db.relationship(
        "CustomerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Memberikan status akun aktif kepada Flask-Login.
    @property
    def is_active(self):
        return self.is_active_account

    # Menyimpan hash password agar password asli tidak disimpan di database.
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Membandingkan password masukan dengan hash yang tersimpan.
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class CustomerProfile(TimestampMixin, db.Model):
    """Data identitas serta dokumen verifikasi milik pelanggan."""

    __tablename__ = "customer_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    gender = db.Column(db.String(20))
    birth_date = db.Column(db.Date)
    address = db.Column(db.Text)
    ktp_number = db.Column(db.String(32), unique=True)
    ktp_image = db.Column(db.String(255))
    sim_number = db.Column(db.String(32))
    sim_type = db.Column(db.String(10))
    sim_image = db.Column(db.String(255))
    profile_image = db.Column(db.String(255))
    emergency_contact = db.Column(db.String(100))
    verification_status = db.Column(
        db.String(30), default="Belum lengkap", nullable=False, index=True
    )
    rejection_reason = db.Column(db.Text)
    user = db.relationship("User", back_populates="profile")


class Category(TimestampMixin, db.Model):
    """Kelompok kendaraan beserta aturan denda keterlambatannya."""

    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(30), nullable=False, index=True)
    description = db.Column(db.Text)
    late_fee_per_day = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    vehicles = db.relationship("Vehicle", back_populates="category")


class Location(TimestampMixin, db.Model):
    """Cabang tempat kendaraan diambil atau dikembalikan."""

    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class Facility(TimestampMixin, db.Model):
    """Fasilitas yang dapat dimiliki oleh banyak kendaraan."""

    __tablename__ = "facilities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    icon = db.Column(db.String(60), default="check-circle")


class Vehicle(TimestampMixin, db.Model):
    """Data utama armada, harga, lokasi, dan status ketersediaan."""

    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True
    )
    location_id = db.Column(
        db.Integer, db.ForeignKey("locations.id"), nullable=False, index=True
    )
    name = db.Column(db.String(120), nullable=False, index=True)
    brand = db.Column(db.String(80), nullable=False, index=True)
    model = db.Column(db.String(80))
    license_plate = db.Column(db.String(20), unique=True, nullable=False)
    chassis_number = db.Column(db.String(80), unique=True)
    engine_number = db.Column(db.String(80), unique=True)
    production_year = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(40))
    passenger_capacity = db.Column(db.Integer, default=2)
    transmission = db.Column(db.String(20), nullable=False, index=True)
    fuel_type = db.Column(db.String(20), nullable=False, index=True)
    daily_price = db.Column(db.Numeric(14, 2), nullable=False)
    deposit = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    last_mileage = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    main_image = db.Column(db.String(255))
    status = db.Column(db.String(30), default="Tersedia", nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    tax_date = db.Column(db.Date)
    registration_expiry = db.Column(db.Date)
    category = db.relationship("Category", back_populates="vehicles")
    location = db.relationship("Location")
    facilities = db.relationship(
        "Facility", secondary=vehicle_facilities, backref="vehicles"
    )
    images = db.relationship(
        "VehicleImage", back_populates="vehicle", cascade="all, delete-orphan"
    )

    # Menghitung rata-rata ulasan yang terlihat, atau nol jika belum ada.
    @property
    def average_rating(self):
        visible = [r.rating for r in self.reviews if r.is_visible]
        return round(sum(visible) / len(visible), 1) if visible else 0


class VehicleImage(TimestampMixin, db.Model):
    """Galeri foto tambahan untuk satu kendaraan."""

    __tablename__ = "vehicle_images"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(
        db.Integer, db.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    filename = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(150))
    vehicle = db.relationship("Vehicle", back_populates="images")


class VehicleSpecification(TimestampMixin, db.Model):
    """Spesifikasi teknis fleksibel untuk katalog kendaraan global."""

    __tablename__ = "vehicle_specifications"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    vehicle_class = db.Column(db.String(60), nullable=False, index=True)
    brand_origin = db.Column(db.String(80), index=True)
    engine_layout = db.Column(db.String(180))
    displacement_cc = db.Column(db.Integer, index=True)
    power_hp = db.Column(db.Numeric(8, 2))
    torque_nm = db.Column(db.Numeric(8, 2))
    gearbox = db.Column(db.String(100))
    final_drive = db.Column(db.String(40))
    fuel_capacity_l = db.Column(db.Numeric(7, 2))
    battery_capacity_kwh = db.Column(db.Numeric(7, 2))
    estimated_range_km = db.Column(db.Integer)
    seat_height_mm = db.Column(db.Integer)
    wet_weight_kg = db.Column(db.Numeric(7, 2))
    ground_clearance_mm = db.Column(db.Integer)
    front_wheel = db.Column(db.String(60))
    rear_wheel = db.Column(db.String(60))
    abs_type = db.Column(db.String(100))
    rider_aids = db.Column(db.Text)
    luggage = db.Column(db.String(180))
    cooling_system = db.Column(db.String(80))
    emission_standard = db.Column(db.String(40))
    source_name = db.Column(db.String(120))
    source_url = db.Column(db.String(500))
    source_checked_at = db.Column(db.DateTime)
    vehicle = db.relationship(
        "Vehicle",
        backref=db.backref(
            "specification", uselist=False, cascade="all, delete-orphan"
        ),
    )


class Driver(TimestampMixin, db.Model):
    """Pengemudi opsional yang dapat dipesan bersama kendaraan."""

    __tablename__ = "drivers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    license_number = db.Column(db.String(40), unique=True, nullable=False)
    address = db.Column(db.Text)
    photo = db.Column(db.String(255))
    daily_rate = db.Column(db.Numeric(14, 2), nullable=False)
    availability_status = db.Column(db.String(20), default="Tersedia", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class Promotion(TimestampMixin, db.Model):
    """Aturan kode promo, periode aktif, nilai diskon, dan kuota."""

    __tablename__ = "promotions"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    discount_type = db.Column(db.String(20), nullable=False)
    discount_value = db.Column(db.Numeric(14, 2), nullable=False)
    max_discount = db.Column(db.Numeric(14, 2))
    minimum_transaction = db.Column(db.Numeric(14, 2), default=0)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    quota = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class RentalInquiry(TimestampMixin, db.Model):
    """Permintaan sewa publik yang menunggu tindak lanjut admin."""

    __tablename__ = "rental_inquiries"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), index=True)
    pickup_location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    nik = db.Column(db.String(16), nullable=False)
    whatsapp = db.Column(db.String(20), nullable=False)
    emergency_phone = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    pickup_time = db.Column(db.Time, nullable=False)
    with_driver = db.Column(db.Boolean, default=False, nullable=False)
    sim_type = db.Column(db.String(20))
    sim_number = db.Column(db.String(32))
    status = db.Column(db.String(30), default="Menunggu konfirmasi", nullable=False, index=True)
    vehicle = db.relationship("Vehicle")
    driver = db.relationship("Driver")
    pickup_location = db.relationship("Location")


class Rental(TimestampMixin, db.Model):
    """Transaksi penyewaan beserta snapshot harga pada saat dipesan."""

    __tablename__ = "rentals"
    id = db.Column(db.Integer, primary_key=True)
    booking_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    customer_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    vehicle_id = db.Column(
        db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True
    )
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), index=True)
    promotion_id = db.Column(db.Integer, db.ForeignKey("promotions.id"))
    pickup_location_id = db.Column(
        db.Integer, db.ForeignKey("locations.id"), nullable=False
    )
    return_location_id = db.Column(
        db.Integer, db.ForeignKey("locations.id"), nullable=False
    )
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    pickup_time = db.Column(db.Time, nullable=False)
    payment_due_at = db.Column(
        db.DateTime, default=default_payment_due_at, nullable=False, index=True
    )
    duration_days = db.Column(db.Integer, nullable=False)
    with_driver = db.Column(db.Boolean, default=False, nullable=False)
    daily_price = db.Column(db.Numeric(14, 2), nullable=False)
    vehicle_subtotal = db.Column(db.Numeric(14, 2), nullable=False)
    driver_fee = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    additional_fee = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    discount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    deposit = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    total_payment = db.Column(db.Numeric(14, 2), nullable=False)
    status = db.Column(
        db.String(50), default="Menunggu pembayaran", nullable=False, index=True
    )
    customer_notes = db.Column(db.Text)
    customer = db.relationship("User", foreign_keys=[customer_id], backref="rentals")
    vehicle = db.relationship("Vehicle", backref="rentals")
    driver = db.relationship("Driver", backref="rentals")
    promotion = db.relationship("Promotion")
    pickup_location = db.relationship("Location", foreign_keys=[pickup_location_id])
    return_location = db.relationship("Location", foreign_keys=[return_location_id])
    status_logs = db.relationship(
        "RentalStatusLog", back_populates="rental", cascade="all, delete-orphan"
    )
    payments = db.relationship(
        "Payment", back_populates="rental", cascade="all, delete-orphan"
    )

    # Menjumlahkan nominal seluruh denda pada transaksi penyewaan.
    @property
    def total_fines(self):
        return sum((f.amount for f in self.fines), Decimal("0"))


class RentalStatusLog(TimestampMixin, db.Model):
    """Riwayat perubahan status sebagai audit trail penyewaan."""

    __tablename__ = "rental_status_logs"
    id = db.Column(db.Integer, primary_key=True)
    rental_id = db.Column(
        db.Integer,
        db.ForeignKey("rentals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50), nullable=False)
    changed_at = db.Column(db.DateTime, default=now, nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    notes = db.Column(db.Text)
    rental = db.relationship("Rental", back_populates="status_logs")
    changed_by = db.relationship("User")


class Payment(TimestampMixin, db.Model):
    """Pembayaran dan hasil verifikasi bukti bayar oleh admin."""

    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    rental_id = db.Column(
        db.Integer,
        db.ForeignKey("rentals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_date = db.Column(db.DateTime, default=now, nullable=False)
    method = db.Column(db.String(30), nullable=False)
    account_holder = db.Column(db.String(120))
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    proof_file = db.Column(db.String(255))
    verification_status = db.Column(
        db.String(20), default="Menunggu", nullable=False, index=True
    )
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    verified_at = db.Column(db.DateTime)
    admin_notes = db.Column(db.Text)
    rental = db.relationship("Rental", back_populates="payments")
    verified_by = db.relationship("User")


class VehiclePickup(TimestampMixin, db.Model):
    """Checklist kondisi kendaraan ketika diserahkan kepada pelanggan."""

    __tablename__ = "vehicle_pickups"
    id = db.Column(db.Integer, primary_key=True)
    rental_id = db.Column(
        db.Integer, db.ForeignKey("rentals.id"), unique=True, nullable=False
    )
    staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    pickup_at = db.Column(db.DateTime, nullable=False)
    start_mileage = db.Column(db.Integer, nullable=False)
    fuel_condition = db.Column(db.String(50))
    body_condition = db.Column(db.Text)
    tire_condition = db.Column(db.String(100))
    light_condition = db.Column(db.String(100))
    cleanliness = db.Column(db.String(100))
    equipment = db.Column(db.Text)
    photo = db.Column(db.String(255))
    notes = db.Column(db.Text)
    customer_approved = db.Column(db.Boolean, default=False)
    rental = db.relationship("Rental", backref=db.backref("pickup", uselist=False))


class VehicleReturn(TimestampMixin, db.Model):
    """Checklist kondisi kendaraan ketika dikembalikan pelanggan."""

    __tablename__ = "vehicle_returns"
    id = db.Column(db.Integer, primary_key=True)
    rental_id = db.Column(
        db.Integer, db.ForeignKey("rentals.id"), unique=True, nullable=False
    )
    staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    returned_at = db.Column(db.DateTime, nullable=False)
    end_mileage = db.Column(db.Integer, nullable=False)
    fuel_condition = db.Column(db.String(50))
    vehicle_condition = db.Column(db.Text)
    equipment = db.Column(db.Text)
    late_days = db.Column(db.Integer, default=0)
    damage_notes = db.Column(db.Text)
    photo = db.Column(db.String(255))
    late_fee = db.Column(db.Numeric(14, 2), default=0)
    damage_fee = db.Column(db.Numeric(14, 2), default=0)
    fuel_fee = db.Column(db.Numeric(14, 2), default=0)
    additional_fee = db.Column(db.Numeric(14, 2), default=0)
    notes = db.Column(db.Text)
    needs_maintenance = db.Column(db.Boolean, default=False)
    rental = db.relationship(
        "Rental", backref=db.backref("vehicle_return", uselist=False)
    )


class Fine(TimestampMixin, db.Model):
    """Denda yang timbul dari keterlambatan atau kerusakan."""

    __tablename__ = "fines"
    id = db.Column(db.Integer, primary_key=True)
    rental_id = db.Column(
        db.Integer, db.ForeignKey("rentals.id"), nullable=False, index=True
    )
    fine_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    description = db.Column(db.Text)
    payment_status = db.Column(db.String(20), default="Belum dibayar")
    rental = db.relationship("Rental", backref="fines")


class PromotionUsage(TimestampMixin, db.Model):
    """Catatan pemakaian promo untuk perhitungan kuota dan audit."""

    __tablename__ = "promotion_usages"
    id = db.Column(db.Integer, primary_key=True)
    promotion_id = db.Column(db.Integer, db.ForeignKey("promotions.id"), nullable=False)
    rental_id = db.Column(
        db.Integer, db.ForeignKey("rentals.id"), unique=True, nullable=False
    )
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    discount_amount = db.Column(db.Numeric(14, 2), nullable=False)


class Maintenance(TimestampMixin, db.Model):
    """Jadwal perawatan yang membuat kendaraan tidak dapat disewa."""

    __tablename__ = "maintenances"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(
        db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True
    )
    maintenance_type = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False, index=True)
    estimated_end_date = db.Column(db.Date, nullable=False)
    actual_end_date = db.Column(db.Date)
    mileage = db.Column(db.Integer)
    cost = db.Column(db.Numeric(14, 2), default=0)
    workshop = db.Column(db.String(150))
    description = db.Column(db.Text)
    proof_file = db.Column(db.String(255))
    status = db.Column(db.String(30), default="Dijadwalkan", nullable=False, index=True)
    vehicle = db.relationship("Vehicle", backref="maintenances")


class Review(TimestampMixin, db.Model):
    """Penilaian pelanggan setelah penyewaan selesai."""

    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    rental_id = db.Column(
        db.Integer, db.ForeignKey("rentals.id"), unique=True, nullable=False
    )
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    review_date = db.Column(db.DateTime, default=now, nullable=False)
    is_visible = db.Column(db.Boolean, default=True, nullable=False)
    customer = db.relationship("User")
    vehicle = db.relationship("Vehicle", backref="reviews")
    rental = db.relationship("Rental", backref=db.backref("review", uselist=False))


class Notification(TimestampMixin, db.Model):
    """Pesan dalam aplikasi yang ditujukan kepada seorang pengguna."""

    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    user = db.relationship("User", backref="notifications")


class AppSetting(TimestampMixin, db.Model):
    """Pasangan key-value untuk pengaturan aplikasi yang dinamis."""

    __tablename__ = "app_settings"
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text)
    description = db.Column(db.String(255))
