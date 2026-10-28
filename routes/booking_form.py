# ==========================================================
# 01. FORMULIR PEMESANAN BERSAMA
# Menangani pesanan pelanggan, tamu, dan petugas dengan validasi serta pencegahan kiriman ganda.
# ==========================================================

"""One booking form for customers, guests, and counter bookings by staff."""

import hashlib
import json
from datetime import datetime
from secrets import token_urlsafe
from uuid import UUID, uuid4

from flask import (
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Driver, Rental, Vehicle
from services.rental_service import PICKUP_CLOSE_TIME, PICKUP_OPEN_TIME, create_rental
from services.identity_service import normalize_booking_phone, validate_identity
from utils.validators import limited_text


# ==========================================================
# 02. KUNCI AKSES PESANAN TAMU
# Menyimpan token acak di sesi dan memakai hash token sebagai pengenal pesanan di database.
# ==========================================================
def guest_session_key(create=False):
    key = session.get("booking_guest_key")
    if not key and create:
        key = token_urlsafe(32)
        session["booking_guest_key"] = key
    return hashlib.sha256(key.encode()).hexdigest() if key else None


# ==========================================================
# 03. MEMPROSES FORMULIR PESANAN
# Menampilkan formulir, memeriksa kiriman ulang dan identitas, lalu membuat pesanan menunggu persetujuan.
# ==========================================================
def booking_form(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, is_active=True).first_or_404()
    customer = (
        current_user
        if current_user.is_authenticated and current_user.role == "pelanggan"
        else None
    )
    guest_key = guest_session_key(create=True) if not customer else None
    request_key = request.form.get("request_key") or str(uuid4())

    def render(error=None, status=200):
        initial = {}
        for key in ["pickup_address", "return_address"]:
            try:
                data = json.loads(request.form.get(key, "null"))
                initial[key] = data if isinstance(data, dict) else None
            except (ValueError, TypeError):
                initial[key] = None
        return (
            render_template(
                "customer/book.html",
                vehicle=vehicle,
                drivers=Driver.query.filter_by(is_active=True).all(),
                request_key=request_key,
                guest_booking=not customer,
                form_data=request.form,
                booking_error=error,
                pickup_open_time=PICKUP_OPEN_TIME.strftime("%H:%M"),
                pickup_close_time=PICKUP_CLOSE_TIME.strftime("%H:%M"),
                **initial,
            ),
            status,
        )

    def fail(message, status=422):
        return (
            render(message, status)
            if request.form.get("response_mode") == "html"
            else (jsonify(error=message), status)
        )

    def success(rental, status=201):
        if current_user.is_authenticated and current_user.role in {"admin", "petugas"}:
            url = url_for("booking_sync.admin_detail", rental_id=rental.id)
        elif customer:
            url = url_for("customer.rental_detail", rental_id=rental.id)
        else:
            url = url_for("public.guest_detail", rental_id=rental.id)
        if request.form.get("response_mode") == "html":
            return redirect(url, code=303)
        return jsonify(url=url, id=rental.id), status

    if request.method == "GET":
        return render()
    try:
        request_key = str(UUID(request_key))
        payload = {
            k: v
            for k, v in request.form.items()
            if k not in {"csrf_token", "request_key", "response_mode"}
        }
        request_hash = hashlib.sha256(
            json.dumps([vehicle_id, payload], sort_keys=True).encode()
        ).hexdigest()
        previous = Rental.query.filter_by(
            customer_id=customer.id if customer else None,
            guest_session_key=guest_key,
            request_key=request_key,
        ).first()
        if previous:
            if previous.request_hash != request_hash:
                return fail(
                    "Pesanan sebelumnya sudah tersimpan. Buka daftar pesanan atau mulai pesanan baru.",
                    409,
                )
            return success(previous, 200)
        if request.form.get("terms") != "1":
            raise ValueError("Setujui syarat penyewaan terlebih dahulu.")
        identity = validate_identity(
            request.form.get("identity_type"),
            request.form.get("identity_number"),
            request.form.get("identity_country", ""),
        )
        guest = None
        if not customer:
            name = limited_text(
                request.form.get("full_name"),
                "Nama penyewa",
                minimum=3,
                maximum=120,
                required=True,
            )
            phone = normalize_booking_phone(request.form.get("phone"))
            guest = dict(name=name, phone=phone, session_key=guest_key)
        start = datetime.strptime(request.form.get("start_date", ""), "%Y-%m-%d").date()
        end = datetime.strptime(request.form.get("end_date", ""), "%Y-%m-%d").date()
        pickup_time = datetime.strptime(
            request.form.get("pickup_time", ""), "%H:%M"
        ).time()
        pickup = json.loads(request.form.get("pickup_address", "null"))
        dropoff = (
            pickup
            if request.form.get("same_location") == "1"
            else json.loads(request.form.get("return_address", "null"))
        )
        driver = None
        if request.form.get("with_driver"):
            driver = db.session.get(Driver, int(request.form.get("driver_id", "0")))
            if not driver or not driver.is_active:
                raise ValueError("Pilih pengemudi yang tersedia.")
        rental = create_rental(
            customer,
            vehicle,
            start,
            end,
            pickup_time,
            None,
            None,
            driver,
            request.form.get("promo_code") if customer else None,
            limited_text(request.form.get("notes"), "Catatan", maximum=1000),
            pickup_address=pickup,
            return_address=dropoff,
            request_key=request_key,
            request_hash=request_hash,
            pending_approval=True,
            guest=guest,
            identity=identity,
        )
        return success(rental)
    except (ValueError, TypeError, KeyError) as error:
        db.session.rollback()
        return fail(str(error))
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error("Booking database failure: %s", type(error).__name__)
        return fail(
            "Database belum dapat menyimpan pesanan. Coba lagi; data formulir tetap tersedia.",
            503,
        )
