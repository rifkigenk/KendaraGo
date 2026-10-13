from datetime import date, timedelta
from decimal import Decimal

import pytest
from flask import Flask

from extensions import db
from models import Category, Location, Vehicle
from routes.public import build_whatsapp_message
from services.report_service import excel_safe
from utils.security import validate_security_config


def test_whatsapp_message_masks_identifiers():
    class Value:
        pass

    vehicle = Value()
    vehicle.daily_price = Decimal("100000")
    vehicle.deposit = Decimal("200000")
    vehicle.name = "Unit Test"
    vehicle.code = "UT-01"
    vehicle.category = Value()
    vehicle.category.name = "Mobil"
    location = Value()
    location.name = "Cabang"
    location.address = "Alamat"
    form = {
        "full_name": "Pelanggan Test",
        "whatsapp": "081234567890",
        "emergency_phone": "081234567899",
        "sim_type": "SIM A",
        "sim_number": "123456789012",
    }

    message = build_whatsapp_message(
        form=form,
        vehicle=vehicle,
        driver=None,
        pickup_location=location,
        start_date=date.today() + timedelta(days=1),
        end_date=date.today() + timedelta(days=2),
        pickup_time=__import__("datetime").time(9, 0),
        nik="1234567890123456",
        detail_url="https://example.com/unit",
    )

    assert "1234567890123456" not in message
    assert "123456789012" not in message
    assert "************3456" in message
    assert "********9012" in message


def test_example_secrets_are_rejected():
    application = Flask(__name__)
    application.config.update(
        SECRET_KEY="ganti_dengan_hasil_secrets_token_hex_32",
        WTF_CSRF_SECRET_KEY="b" * 64,
        FORCE_HTTPS=False,
        SESSION_COOKIE_SECURE=False,
        APP_ENV="development",
    )
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_security_config(application)


@pytest.mark.parametrize("value", ["=CMD()", "+SUM(1,2)", "-1+2", "@IMPORTDATA()"])
def test_excel_formula_input_is_escaped(value):
    assert excel_safe(value).startswith("'")


def test_public_pages_and_missing_image_fallback(app, client):
    category = Category(name="Test", vehicle_type="Mobil", late_fee_per_day=0)
    location = Location(name="Test", address="Alamat")
    vehicle = Vehicle(
        code="IMG-001",
        category=category,
        location=location,
        name="Missing Image",
        brand="Test",
        license_plate="B 2000 TST",
        production_year=2026,
        transmission="Otomatis",
        fuel_type="Bensin",
        daily_price=100000,
        deposit=0,
        main_image="vehicles/not-found.jpg",
        status="Tersedia",
        is_active=True,
    )
    db.session.add_all([category, location, vehicle])
    db.session.commit()

    for path in ("/", "/kendaraan", "/syarat", "/privasi", "/auth/login"):
        response = client.get(path)
        assert response.status_code == 200
    response = client.get("/kendaraan")
    assert b"uploads/vehicles/adventure-bike-green.png" in response.data
