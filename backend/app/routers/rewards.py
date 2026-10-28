"""Community rewards endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_user
from ..models.rewards import RewardClaim, RewardOffer
from ..models.user import User
from ..schemas import EducationIn
from ..serializers import offer_out, recognition_out
from ..services import rewards_service
from ..services.rewards_service import RewardError

router = APIRouter(prefix="/api/rewards", tags=["rewards"])


@router.get("/offers")
def offers(db: Session = Depends(get_db)):
    active = rewards_service.list_active_offers(db)
    # Social proof: how many members claimed each offer (harmless aggregate).
    counts = dict(db.execute(
        select(RewardClaim.offer_id, func.count(RewardClaim.id))
        .group_by(RewardClaim.offer_id)).all())
    return {
        "offers": [{**offer_out(o), "claim_count": counts.get(o.id, 0)} for o in active],
        "notice": ("Rewards recognise community participation. They are never given "
                   "for donating blood and never include cash. Offers labelled "
                   "'Demo Partner' are fictional and not real businesses."),
    }


@router.get("/wallet")
def wallet(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return rewards_service.wallet_payload(db, user.id)


@router.post("/offers/{offer_id}/claim")
def claim(offer_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    try:
        claim = rewards_service.claim_offer(db, user.id, offer_id)
    except RewardError as exc:
        raise HTTPException(422, str(exc))
    offer = db.get(RewardOffer, offer_id)
    return {"claim_code": claim.claim_code, "status": claim.status,
            "offer": offer_out(offer)}


@router.get("/history")
def history(user: User = Depends(require_user), db: Session = Depends(get_db)):
    claims = db.scalars(select(RewardClaim).where(
        RewardClaim.user_id == user.id).order_by(RewardClaim.claimed_at.desc())).all()
    wallet = rewards_service.wallet_payload(db, user.id)
    return {
        "claims": wallet["claims"],
        "recognition": wallet["badges"] + wallet["certificates"] + wallet["education"],
        "claim_count": len(claims),
    }


@router.post("/education/complete")
def education(data: EducationIn, user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    try:
        record, created = rewards_service.complete_education_module(db, user.id, data.module_key)
    except RewardError as exc:
        raise HTTPException(422, str(exc))
    return {"recognition": recognition_out(record), "newly_completed": created}
