"""WhatsApp webhook + status (official WhatsApp Business Cloud API, optional)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import client_ip, rate_limit
from ..services import whatsapp

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/webhook")
def verify(mode: str | None = Query(default=None, alias="hub.mode"),
           token: str | None = Query(default=None, alias="hub.verify_token"),
           challenge: str | None = Query(default=None, alias="hub.challenge")):
    result = whatsapp.verify_challenge(mode, token, challenge)
    if result == 403:
        return Response(status_code=403)
    return Response(content=str(result), media_type="text/plain")


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    # Always ACK quickly (Meta retries on non-2xx); never crash on bad payloads.
    rate_limit(f"wa-webhook:{client_ip(request)}", limit=120, window_seconds=60)
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:  # noqa: BLE001
        return {"received": True, "error": "unparseable payload"}
    outcome = whatsapp.handle_webhook(db, payload)
    return {"received": True, **outcome}


@router.get("/status")
def status():
    return {
        "mode": whatsapp.mode_label(),
        "demo": not whatsapp.is_configured(),
        "demo_notice": whatsapp.DEMO_NOTICE if not whatsapp.is_configured() else None,
        "verify_token_configured": bool(settings.whatsapp_verify_token),
    }
