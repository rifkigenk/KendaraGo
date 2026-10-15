# ==========================================================
# 01. EKSPOR MODEL VEHICLE
# Menyediakan alias model dari entities agar impor melalui modul ini tetap kompatibel.
# ==========================================================

"""Ekspor model kendaraan agar impor lama tetap kompatibel."""

from .entities import (
    Category,
    Facility,
    Location,
    Vehicle,
    VehicleImage,
    VehicleSpecification,
    vehicle_facilities,
)
