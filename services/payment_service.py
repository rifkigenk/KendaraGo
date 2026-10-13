"""Logika bisnis pembuatan dan verifikasi pembayaran penyewaan."""

from datetime import datetime, timedelta
from secrets import token_hex

from flask import current_app
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Payment
from services.rental_service import change_status, payment_deadline_for, utc_now


# =============================================================
# 01. DAFTAR METODE PEMBAYARAN
# requires_proof menentukan apakah pengguna wajib mengunggah bukti.
# =============================================================
PAYMENT_METHODS = {
    "Transfer bank": {"icon": "bank", "requires_proof": True},
    "QRIS": {"icon": "qr-code", "requires_proof": True},
    "GoPay": {"icon": "wallet2", "requires_proof": True},
    "OVO": {"icon": "wallet2", "requires_proof": True},
    "DANA": {"icon": "wallet2", "requires_proof": True},
    "ShopeePay": {"icon": "wallet2", "requires_proof": True},
    "Kartu debit/kredit (EDC)": {"icon": "credit-card", "requires_proof": False},
    "Tunai": {"icon": "cash-stack", "requires_proof": False},
}


# =============================================================
# 02. VALIDASI METODE
# Hanya metode yang terdaftar di atas yang boleh diproses.
# =============================================================
def payment_method_details(method):
    """Mengambil informasi rekening/instruksi untuk metode pembayaran."""
    try:
        return PAYMENT_METHODS[method]
    except KeyError as exception:
        raise ValueError("Pilih metode pembayaran yang tersedia.") from exception


# =============================================================
# 03. PENYIMPANAN PEMBAYARAN
# Membuat nomor pembayaran dan mengubah status pesanan untuk diverifikasi.
# =============================================================
def create_payment(rental, method, account_holder, amount, proof_file):
    """Membuat pembayaran setelah metode, nominal, dan bukti divalidasi."""
    payment_method_details(method)
    if rental.status != "Menunggu pembayaran":
        raise ValueError("Pesanan tidak lagi menerima pembayaran.")
    if payment_deadline_for(rental) <= utc_now():
        raise ValueError("Tenggat pembayaran telah berakhir.")
    if any(item.verification_status == "Menunggu" for item in rental.payments):
        raise ValueError("Sudah ada pembayaran yang menunggu verifikasi.")
    payment = Payment(
        payment_number=f"PAY-{datetime.now():%Y%m%d}-{token_hex(8).upper()}",
        rental_id=rental.id,
        method=method,
        account_holder=account_holder,
        amount=amount,
        proof_file=proof_file,
    )
    db.session.add(payment)
    change_status(
        rental,
        "Menunggu verifikasi pembayaran",
        rental.customer,
        "Bukti pembayaran dikirim",
    )
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ValueError("Pembayaran gagal disimpan. Silakan coba kembali.") from error
    return payment


# =============================================================
# 04. VERIFIKASI ADMIN
# Keputusan admin menentukan pesanan dikonfirmasi atau dikembalikan.
# =============================================================
def verify_payment(payment, admin, accepted, notes=None):
    """Mencatat keputusan admin dan memperbarui status pembayaran."""
    if payment.verification_status != "Menunggu":
        raise ValueError("Pembayaran ini sudah diproses.")
    if payment.rental.status != "Menunggu verifikasi pembayaran":
        raise ValueError("Status pesanan tidak sesuai untuk verifikasi pembayaran.")
    payment.verification_status = "Diverifikasi" if accepted else "Ditolak"
    payment.verified_by_id = admin.id
    payment.verified_at = datetime.now()
    payment.admin_notes = notes
    change_status(
        payment.rental,
        "Dikonfirmasi" if accepted else "Menunggu pembayaran",
        admin,
        notes,
    )
    if not accepted:
        payment.rental.payment_due_at = utc_now() + timedelta(
            hours=current_app.config["PAYMENT_DEADLINE_HOURS"]
        )
    db.session.commit()
