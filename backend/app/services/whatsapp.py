"""WhatsApp integration.

Demo mode (default): the in-app WhatsApp-style chat runs entirely inside
BloodBridge and is clearly labelled as a simulation - nothing is delivered to an
external network.

Official WhatsApp Business Cloud API (optional): when credentials are provided
via environment variables, the webhook verifies challenges, deduplicates message
ids, processes inbound text through the Bridge Assistant and sends replies via
the Graph API. Delivery statuses are recorded idempotently. No automation of
personal accounts, no scraping.
"""
from __future__ import annotations

import json
import logging

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models.misc import ProcessedWebhookMessage
from . import assistant as assistant_service

log = logging.getLogger("bloodbridge.whatsapp")

DEMO_NOTICE = "[Demo Mode - simulated chat inside BloodBridge. No external message was sent.]"


def is_configured() -> bool:
    return bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)


def mode_label() -> str:
    return "whatsapp_cloud_api" if is_configured() else "demo"


def send_text(db: Session, to: str, body: str) -> dict:
    """Send a WhatsApp text message, or simulate it in demo mode."""
    if not is_configured():
        return {"mode": "demo", "delivered": False, "note": DEMO_NOTICE}
    try:
        resp = httpx.post(
            f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": body},
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return {"mode": "cloud_api", "delivered": True, "response": resp.json()}
    except Exception as exc:  # noqa: BLE001 - never crash the webhook on send failure
        log.warning("WhatsApp send failed: %s", exc)
        return {"mode": "cloud_api", "delivered": False, "error": str(exc)}


def verify_challenge(mode: str | None, token: str | None, challenge: str | None) -> str | int:
    """Webhook verification handshake (GET hub.challenge)."""
    if mode == "subscribe" and token and token == settings.whatsapp_verify_token:
        return int(challenge) if (challenge or "").isdigit() else (challenge or "")
    return 403


def _extract_messages(payload: dict) -> list[dict]:
    messages: list[dict] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []) or []:
                messages.append({
                    "id": msg.get("id", ""),
                    "from": msg.get("from", ""),
                    "type": msg.get("type", "unknown"),
                    "text": (msg.get("text", {}) or {}).get("body", ""),
                })
    return messages


def _extract_statuses(payload: dict) -> list[dict]:
    statuses: list[dict] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for status in value.get("statuses", []) or []:
                statuses.append({"id": status.get("id", ""), "status": status.get("status", "")})
    return statuses


def _already_processed(db: Session, message_id: str) -> bool:
    if not message_id:
        return False
    return db.query(ProcessedWebhookMessage).filter(
        ProcessedWebhookMessage.message_id == message_id).first() is not None


def _mark_processed(db: Session, message_id: str, payload: dict) -> None:
    if message_id:
        db.add(ProcessedWebhookMessage(message_id=message_id, payload_json=json.dumps(payload)[:4000]))
        db.commit()


def handle_webhook(db: Session, payload: dict) -> dict:
    """Process an inbound webhook payload. Idempotent per message id."""
    results = {"replies": [], "statuses_recorded": 0, "duplicates_skipped": 0}

    for status in _extract_statuses(payload):
        status_key = f"status:{status['id']}"
        if not _already_processed(db, status_key):
            _mark_processed(db, status_key, {"status": status["status"]})
            results["statuses_recorded"] += 1
        else:
            results["duplicates_skipped"] += 1

    for msg in _extract_messages(payload):
        if _already_processed(db, msg["id"]):
            results["duplicates_skipped"] += 1
            continue
        if msg["type"] not in ("text", "interactive", "button"):
            _mark_processed(db, msg["id"], {"type": msg["type"]})
            continue
        text = msg["text"] or "hello"
        session_id = f"wa:{msg['from']}"
        outcome = assistant_service.handle_message(db, session_id, text, user=None)
        reply = outcome["reply"]
        if not is_configured():
            reply = f"{reply}\n\n{DEMO_NOTICE}"
        send_result = send_text(db, msg["from"], reply)
        _mark_processed(db, msg["id"], {"text": text[:1000]})
        results["replies"].append({"to": msg["from"], "send": send_result,
                                   "assistant_mode": outcome["mode"]})
    return results
