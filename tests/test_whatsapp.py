import hashlib
import hmac
import json
import time
from datetime import timedelta
from types import SimpleNamespace

from extensions import db
from models.entities import now
from models.whatsapp import WhatsAppContact, WhatsAppEvent, WhatsAppOutbox
from services.whatsapp_service import queue_rental_update


def setup_meta(app):
    app.config.update(
        WHATSAPP_ENABLED=True,
        WHATSAPP_APP_SECRET="test-secret",
        WHATSAPP_VERIFY_TOKEN="verify",
        WHATSAPP_PHONE_NUMBER_ID="12345",
        WHATSAPP_PUBLIC_URL="https://example.com",
        WHATSAPP_ACCESS_TOKEN="fake",
        WHATSAPP_API_VERSION="v25.0",
        WHATSAPP_TEMPLATE_NAME="status_pesanan",
    )


def post_message(
    client, body="menu", message_id="wamid.test", signed=True, number_id="12345"
):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": number_id},
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": "628123456789",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/whatsapp",
        data=raw,
        content_type="application/json",
        headers={"X-Hub-Signature-256": signature if signed else "invalid"},
    )


def test_disabled_and_verification(app, client):
    app.config["WHATSAPP_ENABLED"] = False
    assert client.get("/webhooks/whatsapp").status_code == 503
    setup_meta(app)
    assert (
        client.get(
            "/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=bad"
        ).status_code
        == 403
    )
    response = client.get(
        "/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify&hub.challenge=123"
    )
    assert response.data == b"123"


def test_signature_csrf_dedup_and_phone_filter(app, client):
    setup_meta(app)
    app.config["WTF_CSRF_ENABLED"] = True
    assert post_message(client, signed=False).status_code == 403
    assert WhatsAppEvent.query.count() == 0
    assert post_message(client, number_id="other").status_code == 200
    assert WhatsAppOutbox.query.count() == 0
    assert post_message(client).status_code == 200
    assert post_message(client).status_code == 200
    assert WhatsAppOutbox.query.count() == WhatsAppEvent.query.count() == 1
    assert "KendaraGo" in WhatsAppOutbox.query.first().payload["text"]["body"]


def test_consent_transaction_and_opt_out(app, client):
    setup_meta(app)
    rental = SimpleNamespace(
        customer=SimpleNamespace(phone="08123456789"),
        booking_code="BOOK-1",
        status="Dikonfirmasi",
        total_payment=100000,
    )
    queue_rental_update(rental)
    assert WhatsAppOutbox.query.count() == 0
    assert post_message(client, "MULAI").status_code == 200
    assert db.session.get(WhatsAppContact, "628123456789").opted_in
    queue_rental_update(rental)
    db.session.rollback()
    assert WhatsAppOutbox.query.count() == 1
    queue_rental_update(rental)
    db.session.commit()
    assert WhatsAppOutbox.query.count() == 2
    assert post_message(client, "STOP", "wamid.stop").status_code == 200
    queue_rental_update(rental)
    assert WhatsAppOutbox.query.count() == 3


def test_worker_sends_once_cancels_expired_and_respects_stop(app, monkeypatch):
    setup_meta(app)
    sent = []

    def fake_send(row):
        sent.append(row.id)
        return "meta-id"

    monkeypatch.setattr("services.whatsapp_service.send_message", fake_send)
    for payload, expiry in [
        ({"type": "text"}, now() + timedelta(hours=1)),
        ({"type": "text"}, now() - timedelta(hours=1)),
        ({"type": "template"}, now() + timedelta(hours=1)),
    ]:
        db.session.add(
            WhatsAppOutbox(phone="628123456789", payload=payload, expires_at=expiry)
        )
    db.session.commit()
    runner = app.test_cli_runner()
    assert runner.invoke(args=["whatsapp-send"]).exit_code == 0
    assert runner.invoke(args=["whatsapp-send"]).exit_code == 0
    assert len(sent) == 1
    assert WhatsAppOutbox.query.filter_by(status="cancelled").count() == 2


def test_worker_timeout_not_retried(app, monkeypatch):
    setup_meta(app)

    def timeout(row):
        raise TimeoutError()

    monkeypatch.setattr("services.whatsapp_service.send_message", timeout)
    db.session.add(
        WhatsAppOutbox(
            phone="628123456789",
            payload={"type": "text"},
            expires_at=now() + timedelta(hours=1),
        )
    )
    db.session.commit()
    assert app.test_cli_runner().invoke(args=["whatsapp-send"]).exit_code == 0
    assert WhatsAppOutbox.query.one().status == "unknown"


def test_status_links_to_authenticated_portal(app, client):
    setup_meta(app)
    assert post_message(client, "STATUS BOOK-OTHER").status_code == 200
    reply = WhatsAppOutbox.query.one().payload["text"]["body"]
    assert "https://example.com/pelanggan/" in reply
    assert "BOOK-OTHER" not in reply
