"""Audit helpers + in-app notifications."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.misc import Notification
from ..models.rewards import RewardAuditLog
from ..models.referral import ReferralAuditLog


def log_reward_action(db: Session, action: str, actor_id: int | None = None,
                      target_type: str = "", target_id: str = "", reason: str = "") -> None:
    db.add(RewardAuditLog(action=action, actor_id=actor_id, target_type=target_type,
                          target_id=str(target_id), reason=reason))


def log_referral_action(db: Session, action: str, actor_id: int | None = None,
                        target_id: str = "", reason: str = "") -> None:
    db.add(ReferralAuditLog(action=action, actor_id=actor_id, target_id=str(target_id), reason=reason))


def notify(db: Session, user_id: int | None, ntype: str, title: str, body: str = "", link: str = "") -> None:
    if user_id is None:
        return
    db.add(Notification(user_id=user_id, ntype=ntype, title=title, body=body, link=link))
