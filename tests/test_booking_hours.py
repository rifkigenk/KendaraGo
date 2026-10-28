"""Booking hours are enforced for direct submissions as well as the form."""

import pytest

from models import Rental
from test_bali_locations import booking_form
from test_rental_flow import rental_data


@pytest.mark.parametrize(
    "pickup_time,expected_status",
    [("09:59", 422), ("10:00", 201), ("15:35", 201), ("21:00", 201), ("21:01", 422)],
)
def test_booking_operating_hours(app, client, pickup_time, expected_status):
    _, vehicle, _, _ = rental_data()
    response = client.post(
        f"/kendaraan/{vehicle.id}/pesan",
        data={
            **booking_form(),
            "full_name": "Penyewa Fixture",
            "phone": "081234567890",
            "pickup_time": pickup_time,
        },
    )
    assert response.status_code == expected_status, response.json
    if expected_status == 422:
        assert "10.00 dan 21.00" in response.json["error"]
        assert Rental.query.count() == 0
    else:
        assert Rental.query.one().pickup_time.strftime("%H:%M") == pickup_time


def test_booking_hours_error_preserves_form(app, client):
    _, vehicle, _, _ = rental_data()
    response = client.post(
        f"/kendaraan/{vehicle.id}/pesan",
        data={
            **booking_form(),
            "full_name": "Penyewa Fixture",
            "phone": "081234567890",
            "pickup_time": "09:00",
            "response_mode": "html",
        },
    )
    assert response.status_code == 422
    assert 'min="10:00" max="21:00"' in response.text
    assert "Jam operasional 10.00–21.00" in response.text
    assert 'value="Penyewa Fixture"' in response.text
    assert 'value="09:00"' in response.text
    assert Rental.query.count() == 0
