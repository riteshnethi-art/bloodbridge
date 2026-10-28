"""Account-level endpoints: onboarding and notifications."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_user
from ..models.misc import Notification
from ..models.user import User
from ..serializers import notification_out
from ..services import referral_service, rewards_service
from ..services.audit import notify

router = APIRouter(prefix="/api", tags=["account"])


@router.post("/onboarding/complete")
def complete_onboarding(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Marks community onboarding complete and issues a welcome badge (idempotent).
    Also evaluates referral eligibility for users who joined via an invite."""
    if user.onboarding_completed:
        return {"onboarding_completed": True, "already_completed": True,
                "referral": referral_service.record_onboarding(db, user)}
    user.onboarding_completed = True
    rewards_service.issue_recognition(
        db, user.id, kind="badge", title="Community Onboarding",
        description="Completed BloodBridge community onboarding, including the "
                    "participation and safety guidelines.",
        source="onboarding", meta={"step": "onboarding"},
    )
    notify(db, user.id, "onboarding", "Welcome to the BloodBridge community",
           "Your onboarding badge has been added to your rewards wallet.",
           link="/rewards")
    db.commit()
    referral = referral_service.record_onboarding(db, user)
    return {"onboarding_completed": True, "already_completed": False, "referral": referral}


@router.get("/notifications")
def notifications(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(
        Notification.user_id == user.id).order_by(
        Notification.created_at.desc()).limit(50)).all()
    unread = db.scalars(select(Notification).where(
        Notification.user_id == user.id, Notification.read.is_(False))).all()
    return {"notifications": [notification_out(n) for n in rows],
            "unread_count": len(unread)}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(require_user), db: Session = Depends(get_db)):
    unread = db.scalars(select(Notification).where(
        Notification.user_id == user.id, Notification.read.is_(False))).all()
    for n in unread:
        n.read = True
    db.commit()
    return {"marked_read": len(unread)}
