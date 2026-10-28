"""Authentication routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import client_ip, get_current_user, rate_limit, require_user
from ..models.user import User
from ..schemas import AuthOut, LoginIn, RegisterIn, UserOut
from ..security import create_token, hash_password, verify_password
from ..services import referral_service
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"register:{client_ip(request)}", limit=20, window_seconds=3600)
    email = data.email.lower().strip()
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(409, "An account with this email already exists")
    user = User(
        name=data.name.strip(),
        email=email,
        phone=(data.phone or "").strip() or None,
        password_hash=hash_password(data.password),
        role=data.role,
        # Demo mode: verification is simulated. Production must verify for real.
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    attributed = None
    if data.referral_code:
        try:
            attributed = referral_service.attribute(db, data.referral_code.strip().upper(), user)
        except referral_service.ReferralError as exc:
            raise HTTPException(400, str(exc))

    return AuthOut(
        token=create_token(user.id, user.role),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=AuthOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"login:{client_ip(request)}", limit=10, window_seconds=60)
    user = db.scalars(select(User).where(User.email == data.email.lower().strip())).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return AuthOut(token=create_token(user.id, user.role), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user)):
    return UserOut.model_validate(user)
