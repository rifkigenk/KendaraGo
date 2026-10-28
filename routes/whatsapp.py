# ==========================================================
# 01. PENERIMA WEBHOOK WHATSAPP
# Memverifikasi permintaan Meta, menyaring pesan ganda, dan menyimpan balasan ke antrean database.
# ==========================================================

"""Signed Meta webhook; replies are queued durably before acknowledging."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, request
from sqlalchemy.exc import IntegrityError

from extensions import csrf, db
from models.entities import now
from models.whatsapp import WhatsAppEvent
from services.whatsapp_service import bot_reply, phone_number, queue_message

bp = Blueprint("whatsapp", __name__)


# ==========================================================
# 02. VERIFIKASI DAN PENERIMAAN PESAN META
# Memeriksa token GET atau signature POST, menyaring pesan, dan mengantrekan balasan sebelum respons sukses.
# ==========================================================
@bp.route("/webhooks/whatsapp", methods=["GET", "POST"])
@csrf.exempt
def webhook():
    config = current_app.config
    if not config["WHATSAPP_ENABLED"]:
        return {"error": "WhatsApp belum aktif"}, 503
    if request.method == "GET":
        token = config["WHATSAPP_VERIFY_TOKEN"]
        if (
            token
            and request.args.get("hub.mode") == "subscribe"
            and hmac.compare_digest(request.args.get("hub.verify_token", ""), token)
        ):
            return (
                request.args.get("hub.challenge", ""),
                200,
                {"Content-Type": "text/plain"},
            )
        return {"error": "Verifikasi ditolak"}, 403
    secret = config["WHATSAPP_APP_SECRET"]
    signature = (
        "sha256="
        + hmac.new(secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
    )
    if not secret or not hmac.compare_digest(
        signature, request.headers.get("X-Hub-Signature-256", "")
    ):
        return {"error": "Signature tidak valid"}, 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get("object") != "whatsapp_business_account":
        return {"error": "Payload tidak valid"}, 400
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if (
                    value.get("metadata", {}).get("phone_number_id")
                    != config["WHATSAPP_PHONE_NUMBER_ID"]
                ):
                    continue
                for message in value.get("messages", []):
                    message_id = message.get("id")
                    phone = phone_number(message.get("from"))
                    if (
                        not phone
                        or not isinstance(message_id, str)
                        or len(message_id) > 255
                    ):
                        continue
                    timestamp = datetime.fromtimestamp(
                        int(message["timestamp"]), timezone.utc
                    ).replace(tzinfo=None)
                    expires_at = timestamp + timedelta(hours=23)
                    if expires_at <= now() or timestamp > now() + timedelta(minutes=5):
                        continue
                    try:
                        with db.session.begin_nested():
                            db.session.add(WhatsAppEvent(message_id=message_id))
                            db.session.flush()
                            body = (
                                message.get("text", {}).get("body", "")
                                if message.get("type") == "text"
                                else ""
                            )
                            reply = bot_reply(phone, body)
                            queue_message(
                                phone,
                                {"type": "text", "text": {"body": reply}},
                                expires_at,
                            )
                    except IntegrityError:
                        if db.session.get(WhatsAppEvent, message_id) is None:
                            raise
        db.session.commit()
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
        db.session.rollback()
        return {"error": "Payload tidak valid"}, 400
    return {"status": "ok"}
