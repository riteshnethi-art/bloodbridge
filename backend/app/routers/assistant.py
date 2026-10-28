"""Bridge Assistant endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_ip, get_current_user, rate_limit
from ..models.user import User
from ..schemas import AssistantMessageIn
from ..services import assistant

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/message")
def message(data: AssistantMessageIn, request: Request, db: Session = Depends(get_db),
            user: User | None = Depends(get_current_user)):
    rate_limit(f"assistant:{client_ip(request)}", limit=60, window_seconds=60)
    return assistant.handle_message(db, data.session_id.strip(), data.message, user)
