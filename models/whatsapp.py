# ==========================================================
# 01. PENYIMPANAN INTEGRASI WHATSAPP
# Mendefinisikan persetujuan kontak, penanda pesan masuk, dan antrean pengiriman keluar.
# ==========================================================

"""Persistent WhatsApp consent, webhook deduplication, and transactional outbox."""

from extensions import db
from models.entities import now


# ==========================================================
# 02. PERSETUJUAN NOTIFIKASI KONTAK
# Menyimpan nomor telepon, pilihan berlangganan, dan waktu perubahan persetujuan.
# ==========================================================
class WhatsAppContact(db.Model):
    __tablename__ = "whatsapp_contacts"
    phone = db.Column(db.String(20), primary_key=True)
    opted_in = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=now)


# ==========================================================
# 03. PENANDA PESAN MASUK
# Memakai ID pesan sebagai kunci utama agar webhook yang dikirim ulang tidak diproses dua kali.
# ==========================================================
class WhatsAppEvent(db.Model):
    __tablename__ = "whatsapp_events"
    message_id = db.Column(db.String(255), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


# ==========================================================
# 04. ANTREAN PESAN KELUAR
# Menyimpan tujuan, payload, batas kedaluwarsa, status kirim, dan hasil dari Meta.
# ==========================================================
class WhatsAppOutbox(db.Model):
    __tablename__ = "whatsapp_outbox"
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    expires_at = db.Column(db.DateTime, nullable=False)
    meta_message_id = db.Column(db.String(255))
    error = db.Column(db.String(120))
