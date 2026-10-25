"""Meta Cloud API bot and outbox. Never send network requests inside bookings."""

import json
import re
from datetime import timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import click
from flask import current_app

from extensions import db
from models.entities import now
from models.whatsapp import WhatsAppContact, WhatsAppOutbox


def phone_number(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    return digits if re.fullmatch(r"[1-9][0-9]{7,14}", digits) else None


def queue_message(phone, payload, expires_at):
    db.session.add(WhatsAppOutbox(phone=phone, payload=payload, expires_at=expires_at))


def bot_reply(phone, body):
    command = body.strip().upper()
    base = current_app.config["WHATSAPP_PUBLIC_URL"].rstrip("/")
    if command in {"MULAI", "STOP"}:
        contact = db.session.get(WhatsAppContact, phone)
        if contact is None:
            contact = WhatsAppContact(phone=phone)
            db.session.add(contact)
        contact.opted_in = command == "MULAI"
        contact.updated_at = now()
        return (
            "Notifikasi transaksi diaktifkan. Ketik STOP untuk berhenti."
            if contact.opted_in
            else "Notifikasi transaksi dihentikan. Ketik MULAI untuk berlangganan kembali."
        )
    if command == "1":
        return f"Lihat kendaraan, harga, dan pilih tanggal sewa di {base}/kendaraan"
    if command == "2" or command.startswith("STATUS"):
        return f"Untuk menjaga privasi, masuk ke akun KendaraGo untuk melihat pesanan Anda: {base}/pelanggan/"
    if command == "3":
        return f"Hubungi petugas melalui halaman kontak: {base}/kontak. Bot ini belum menyediakan percakapan langsung dengan petugas."
    return (
        "Selamat datang di KendaraGo!\n"
        "1. Lihat kendaraan\n2. Cek pesanan\n3. Hubungi petugas\n"
        "Ketik MULAI untuk menyetujui notifikasi transaksi ke nomor ini. "
        "Ketik STOP untuk berhenti.\nKirim angka pilihan Anda."
    )


def queue_rental_update(rental):
    config = current_app.config
    if not config["WHATSAPP_ENABLED"] or not config["WHATSAPP_TEMPLATE_NAME"]:
        return
    phone = phone_number(rental.customer_phone)
    contact = db.session.get(WhatsAppContact, phone) if phone else None
    if not contact or not contact.opted_in:
        return
    # The approved template has exactly three body variables, in this order.
    payload = {
        "type": "template",
        "template": {
            "name": config["WHATSAPP_TEMPLATE_NAME"],
            "language": {"code": config["WHATSAPP_TEMPLATE_LANGUAGE"]},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(value)}
                        for value in (
                            rental.booking_code,
                            rental.status,
                            f"Rp {rental.total_payment:,.0f}",
                        )
                    ],
                }
            ],
        },
    }
    queue_message(phone, payload, now() + timedelta(hours=24))


def send_message(row):
    config = current_app.config
    version = config["WHATSAPP_API_VERSION"]
    number_id = config["WHATSAPP_PHONE_NUMBER_ID"]
    if not re.fullmatch(r"v\d+\.\d+", version) or not number_id.isdigit():
        raise ValueError("invalid_configuration")
    payload = {"messaging_product": "whatsapp", "to": row.phone, **row.payload}
    request = Request(
        f"https://graph.facebook.com/{version}/{number_id}/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {config['WHATSAPP_ACCESS_TOKEN']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)["messages"][0]["id"]


@click.command("whatsapp-send")
@click.option("--limit", default=50, type=click.IntRange(1, 500))
def send_pending(limit):
    """Process a bounded batch. Schedule every minute; no automatic ambiguous retries."""
    config = current_app.config
    if not config["WHATSAPP_ENABLED"] or not all(
        config[key]
        for key in (
            "WHATSAPP_ACCESS_TOKEN",
            "WHATSAPP_PHONE_NUMBER_ID",
            "WHATSAPP_API_VERSION",
        )
    ):
        raise click.ClickException(
            "WhatsApp belum aktif atau kredensial Meta belum lengkap."
        )
    ids = db.session.scalars(
        db.select(WhatsAppOutbox.id)
        .where(WhatsAppOutbox.status == "pending")
        .order_by(WhatsAppOutbox.id)
        .limit(limit)
    ).all()
    counts = {}
    for message_id in ids:
        # Atomic claim prevents two scheduler processes from sending the same row.
        claimed = db.session.execute(
            db.update(WhatsAppOutbox)
            .where(WhatsAppOutbox.id == message_id, WhatsAppOutbox.status == "pending")
            .values(status="sending")
        ).rowcount
        db.session.commit()
        if not claimed:
            continue
        row = db.session.get(WhatsAppOutbox, message_id)
        contact = db.session.get(WhatsAppContact, row.phone)
        if row.expires_at <= now() or (
            row.payload["type"] == "template" and (not contact or not contact.opted_in)
        ):
            row.status = "cancelled"
        else:
            try:
                row.meta_message_id = send_message(row)
                row.status = "accepted"
            except HTTPError as error:
                row.status, row.error = "failed", f"HTTP {error.code}"
            except (URLError, TimeoutError, OSError, ValueError, KeyError, IndexError):
                row.status, row.error = "unknown", "Periksa Meta sebelum mengirim ulang"
        db.session.commit()
        counts[row.status] = counts.get(row.status, 0) + 1
    click.echo(json.dumps(counts))
