"""Referral program endpoints ("BloodBridge Community Invites")."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..deps import require_user
from ..models.referral import ReferralAttribution, ReferralCampaign
from ..models.user import User
from ..schemas import AttributeIn, TrackIn
from ..services import referral_service
from ..services.referral_service import ReferralError

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


@router.get("/me")
def my_code(user: User = Depends(require_user), db: Session = Depends(get_db)):
    code_row = referral_service.ensure_referral_code(db, user)
    return {
        "code": code_row.code,
        "link": referral_service.referral_link(code_row.code),
        "status": code_row.status,
        "invitation_message": (
            "Join BloodBridge, a community platform that helps people discover "
            "potential blood donors and access blood-request resources. Use my "
            f"invite link to join: {referral_service.referral_link(code_row.code)}"
        ),
        "disclaimer": ("Joining BloodBridge does not guarantee access to blood, donors "
                       "or any medical service. Referral recognition is non-cash and "
                       "never tied to blood donation."),
    }


@router.post("/code")
def create_code(user: User = Depends(require_user), db: Session = Depends(get_db)):
    code_row = referral_service.ensure_referral_code(db, user)
    return {"code": code_row.code, "link": referral_service.referral_link(code_row.code)}


@router.get("/stats")
def stats(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return referral_service.stats_for_user(db, user)


@router.get("/history")
def history(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return referral_service.history_for_user(db, user)


@router.get("/campaigns")
def campaigns(db: Session = Depends(get_db)):
    now = utcnow()
    rows = db.scalars(select(ReferralCampaign).where(
        ReferralCampaign.status == "active")).all()
    visible = [c for c in rows
               if (c.start_at is None or c.start_at <= now)
               and (c.end_at is None or c.end_at >= now)]
    return {"campaigns": [_campaign_out(c) for c in visible]}


def _campaign_out(c: ReferralCampaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "start_at": c.start_at.isoformat() if c.start_at else None,
        "end_at": c.end_at.isoformat() if c.end_at else None,
        "eligible_event": c.eligible_event,
        "reward_type": c.reward_type,
        "eligibility_rules": c.eligibility_rules,
        "terms": c.terms,
        "status": c.status,
    }


@router.post("/track")
def track(data: TrackIn, db: Session = Depends(get_db)):
    """Public: record link_opened / registration_started events from the /join page.

    The page supplies a stable per-visit `reference` so retries deduplicate;
    without one, each call counts as a distinct measurable event.
    """
    try:
        created = referral_service.track_event(db, data.code.strip().upper(),
                                               data.event_type, reference=data.reference or "")
    except ReferralError as exc:
        raise HTTPException(422, str(exc))
    return {"recorded": created}


@router.post("/attribute")
def attribute(data: AttributeIn, user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    """Attribute the signed-in user to a referral code (if not already attributed
    and the account is recent)."""
    existing = db.scalars(select(ReferralAttribution).where(
        ReferralAttribution.referred_user_id == user.id)).first()
    if existing:
        return {"attributed": True, "already_attributed": True, "status": existing.status}
    if user.created_at and user.created_at < utcnow() - timedelta(days=7):
        raise HTTPException(422, "Referral codes can only be applied within 7 days of registration")
    try:
        attribution = referral_service.attribute(db, data.code.strip().upper(), user,
                                                 source=data.source)
    except ReferralError as exc:
        raise HTTPException(422, str(exc))
    if not attribution:
        raise HTTPException(404, "Referral code not found")
    return {"attributed": True, "already_attributed": False, "status": attribution.status}
