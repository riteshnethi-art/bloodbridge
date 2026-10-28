"""Referral program service ("BloodBridge Community Invites").

Principles enforced here (in addition to the API layer):
- Referral rewards are non-cash recognition only. Cash-like reward types are
  rejected defensively.
- Rewards are never tied to donating blood, donor availability, match
  acceptance or request fulfilment.
- One referrer per referred account, self-referrals blocked, duplicate-account
  signals flagged for human review (never auto-banned), events idempotent,
  campaign limits enforced transactionally.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import uuid4

from ..config import settings
from ..database import utcnow
from ..models.referral import (
    ReferralAttribution, ReferralAuditLog, ReferralCampaign, ReferralCode,
    ReferralEvent, ReferralReward,
)
from ..models.rewards import RecognitionRecord
from ..models.user import User
from .audit import log_referral_action, notify
from .rewards_service import issue_recognition
from ..security import generate_code

ALLOWED_REWARD_TYPES = {"badge", "certificate", "educational"}
EVENT_TYPES = (
    "link_opened", "registration_started", "account_created", "contact_verified",
    "onboarding_completed", "referral_reviewed", "eligible", "rejected",
)


class ReferralError(ValueError):
    pass


# ---------------------------------------------------------------- codes

def ensure_referral_code(db: Session, user: User) -> ReferralCode:
    code_row = db.scalars(select(ReferralCode).where(ReferralCode.user_id == user.id)).first()
    if code_row:
        return code_row
    for _ in range(10):
        candidate = f"BLOODBRIDGE-{generate_code(5)}"
        if not db.scalars(select(ReferralCode).where(ReferralCode.code == candidate)).first():
            code_row = ReferralCode(user_id=user.id, code=candidate)
            db.add(code_row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            db.refresh(code_row)
            return code_row
    raise ReferralError("Could not generate a unique referral code")


def referral_link(code: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}/join?ref={code}"


# ---------------------------------------------------------------- tracking

def track_event(db: Session, code: str, event_type: str, reference: str = "",
                attribution_id: int | None = None) -> bool:
    """Record a measurable referral event. Idempotent per (attribution, type, ref).

    Pre-registration events (link_opened, registration_started) are keyed by the
    code string in event_reference because no attribution exists yet.
    Returns True if a new event was recorded.
    """
    if event_type not in EVENT_TYPES:
        raise ReferralError("Unknown event type")
    if attribution_id is None:
        code_row = db.scalars(select(ReferralCode).where(ReferralCode.code == code)).first()
        if not code_row:
            return False
        if not reference:
            # Each measurable open/visit is a distinct event; the code is embedded
            # as a prefix so stats can attribute pre-registration events.
            reference = uuid4().hex[:10]
        reference = f"{code}:{reference}"
    existing = db.scalars(select(ReferralEvent).where(
        ReferralEvent.attribution_id == attribution_id,
        ReferralEvent.event_type == event_type,
        ReferralEvent.event_reference == reference,
    )).first()
    if existing:
        return False
    db.add(ReferralEvent(attribution_id=attribution_id, event_type=event_type,
                         event_reference=reference, verification_status="measured"))
    db.commit()
    return True


def attribute(db: Session, code: str, new_user: User, source: str = "link") -> ReferralAttribution | None:
    """Attach a new account to a referrer. Idempotent; flags suspicious signals."""
    code_row = db.scalars(select(ReferralCode).where(ReferralCode.code == code)).first()
    if not code_row:
        return None
    referrer = db.get(User, code_row.user_id)
    if not referrer:
        return None
    if referrer.id == new_user.id:
        raise ReferralError("Self-referrals are not allowed")

    existing = db.scalars(select(ReferralAttribution).where(
        ReferralAttribution.referred_user_id == new_user.id)).first()
    if existing:
        return existing  # one referrer per account - ignore later codes

    flags: list[str] = []
    if new_user.phone and referrer.phone and new_user.phone == referrer.phone:
        flags.append("phone_matches_referrer")
    local_new = (new_user.email or "").split("@")[0].lower()
    local_ref = (referrer.email or "").split("@")[0].lower()
    if new_user.email and referrer.email and len(local_new) >= 4 and (
        local_new == local_ref or (local_ref in local_new) or (local_new in local_ref)
    ):
        flags.append("email_similar_to_referrer")

    attribution = ReferralAttribution(
        referrer_user_id=referrer.id,
        referred_user_id=new_user.id,
        referral_code_id=code_row.id,
        attribution_source=source if source in ("link", "invitation_message", "manual_entry", "assistant") else "link",
        status="pending",
        flag_reasons=",".join(flags),
    )
    db.add(attribution)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalars(select(ReferralAttribution).where(
            ReferralAttribution.referred_user_id == new_user.id)).first()
    db.refresh(attribution)
    log_referral_action(db, "referral_attributed", actor_id=new_user.id,
                        target_id=str(attribution.id), reason=f"code={code}")
    track_event(db, code, "account_created", reference=str(new_user.id), attribution_id=attribution.id)
    if new_user.email_verified:
        track_event(db, code, "contact_verified", reference=str(new_user.id), attribution_id=attribution.id)
    db.commit()
    return attribution


def record_onboarding(db: Session, user: User) -> dict:
    """Called when a user completes community onboarding; evaluates eligibility."""
    attribution = db.scalars(select(ReferralAttribution).where(
        ReferralAttribution.referred_user_id == user.id)).first()
    result = {"attributed": False, "status": None, "reward": None}
    if not attribution:
        return result
    result["attributed"] = True
    track_event(db, "", "onboarding_completed", reference=str(user.id),
                attribution_id=attribution.id)
    _evaluate(db, attribution)
    result["status"] = attribution.status
    reward = db.scalars(select(ReferralReward).where(
        ReferralReward.attribution_id == attribution.id)).first()
    if reward:
        result["reward"] = {"type": reward.reward_type, "status": reward.status}
    return result


# ---------------------------------------------------------------- eligibility

def _campaign_for_event(db: Session, event: str) -> ReferralCampaign | None:
    now = utcnow()
    campaigns = db.scalars(select(ReferralCampaign).where(
        ReferralCampaign.status == "active",
        ReferralCampaign.eligible_event == event,
    )).all()
    for c in campaigns:
        if c.start_at and c.start_at > now:
            continue
        if c.end_at and c.end_at < now:
            continue
        return c
    return None


def _evaluate(db: Session, attribution: ReferralAttribution) -> None:
    """Server-side eligibility evaluation. Runs after onboarding completion."""
    if attribution.status in ("approved", "rejected"):
        return
    referred = db.get(User, attribution.referred_user_id)
    if not referred:
        return
    # Hard requirements
    if not referred.email_verified:
        attribution.status = "pending"
        db.commit()
        return
    if not referred.onboarding_completed:
        attribution.status = "pending"
        db.commit()
        return
    if attribution.flag_reasons:
        attribution.status = "under_review"
        db.commit()
        notify(db, attribution.referrer_user_id, "referral_review",
               "Referral pending review",
               "A referral of yours is undergoing a routine abuse-prevention review.",
               link="/referrals")
        return

    campaign = _campaign_for_event(db, "onboarding_completed")
    if not campaign:
        attribution.status = "eligible"
        db.commit()
        track_event(db, "", "eligible", reference=str(attribution.id), attribution_id=attribution.id)
        return

    if campaign.reward_type not in ALLOWED_REWARD_TYPES:
        # Policy violation: refuse loudly rather than silently degrading.
        raise ReferralError(f"Reward type '{campaign.reward_type}' is not permitted. "
                            "Only non-cash recognition is allowed.")

    if campaign.requires_review and not campaign.auto_approve:
        attribution.status = "under_review"
        db.commit()
        notify(db, attribution.referrer_user_id, "referral_review",
               "Referral ready for review",
               "A referral of yours completed onboarding and is awaiting review.",
               link="/referrals")
        return

    try:
        _issue_reward(db, attribution, campaign, approver_id=None)
    except ReferralError as exc:
        # Eligible in principle, but limits or policy blocked issuance.
        attribution.status = "eligible"
        log_referral_action(db, "reward_not_issued", actor_id=None,
                            target_id=str(attribution.id), reason=str(exc))
        db.commit()


def _issue_reward(db: Session, attribution: ReferralAttribution,
                  campaign: ReferralCampaign, approver_id: int | None) -> ReferralReward:
    if campaign.reward_type not in ALLOWED_REWARD_TYPES:
        raise ReferralError(f"Reward type '{campaign.reward_type}' is not permitted. "
                            "Only non-cash recognition is allowed.")
    # Limits (re-checked inside the transaction)
    referrer_count = db.scalar(select(func.count(ReferralReward.id)).join(
        ReferralAttribution, ReferralReward.attribution_id == ReferralAttribution.id
    ).where(ReferralAttribution.referrer_user_id == attribution.referrer_user_id,
            ReferralReward.campaign_id == campaign.id,
            ReferralReward.status != "rejected"))
    if referrer_count >= campaign.per_user_limit:
        raise ReferralError("Referrer has reached the campaign limit")
    if campaign.times_issued >= campaign.total_limit:
        raise ReferralError("Campaign limit reached")

    existing = db.scalars(select(ReferralReward).where(
        ReferralReward.attribution_id == attribution.id)).first()
    if existing:
        return existing

    reward = ReferralReward(
        attribution_id=attribution.id,
        campaign_id=campaign.id,
        reward_type=campaign.reward_type,
        status="issued",
        issued_at=utcnow(),
        approved_by=approver_id,
    )
    campaign.times_issued += 1
    db.add(reward)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ReferralError("A reward already exists for this referral")

    attribution.status = "approved"
    track_event(db, "", "eligible", reference=str(attribution.id), attribution_id=attribution.id)

    referred = db.get(User, attribution.referred_user_id)
    titles = {
        "badge": "Community Connector Badge",
        "certificate": "Community Invitation Certificate",
        "educational": "Community Growth Recognition",
    }
    issue_recognition(
        db, attribution.referrer_user_id, kind=campaign.reward_type,
        title=titles.get(campaign.reward_type, "Community Recognition"),
        description=(f"Awarded by campaign '{campaign.name}' for inviting a new member "
                     "who completed community onboarding. This is non-cash community "
                     "recognition - it is not tied to blood donation in any way."),
        source="referral_campaign", meta={"campaign_id": campaign.id},
    )
    notify(db, attribution.referrer_user_id, "referral_reward",
           "Referral recognition issued",
           f"Your invite led to a completed community onboarding. Recognition added "
           f"to your rewards wallet (campaign: {campaign.name}).", link="/referrals")
    log_referral_action(db, "referral_reward_issued", actor_id=approver_id,
                        target_id=str(attribution.id), reason=campaign.name)
    db.commit()
    return reward


# ---------------------------------------------------------------- admin review

def review_referral(db: Session, attribution_id: int, approve: bool, reason: str,
                    admin: User) -> ReferralAttribution:
    attribution = db.get(ReferralAttribution, attribution_id)
    if not attribution:
        raise ReferralError("Referral not found")
    if attribution.status in ("approved", "rejected"):
        raise ReferralError("Referral already reviewed")
    if approve:
        campaign = _campaign_for_event(db, "onboarding_completed")
        if not campaign:
            # Fall back to the most recent active/any campaign for manual approval
            campaign = db.scalars(select(ReferralCampaign).order_by(
                ReferralCampaign.created_at.desc())).first()
        if not campaign:
            raise ReferralError("No campaign configured - cannot issue a reward")
        _issue_reward(db, attribution, campaign, approver_id=admin.id)
        track_event(db, "", "referral_reviewed", reference=f"approved:{admin.id}",
                    attribution_id=attribution.id)
    else:
        if not reason.strip():
            raise ReferralError("A rejection reason is required")
        attribution.status = "rejected"
        track_event(db, "", "rejected", reference=reason[:60], attribution_id=attribution.id)
        log_referral_action(db, "referral_rejected", actor_id=admin.id,
                            target_id=str(attribution.id), reason=reason)
        notify(db, attribution.referrer_user_id, "referral_review",
               "Referral was not approved", f"Reason: {reason}", link="/referrals")
        db.commit()
    db.refresh(attribution)
    return attribution


# ---------------------------------------------------------------- dashboards

def stats_for_user(db: Session, user: User) -> dict:
    code_row = ensure_referral_code(db, user)
    attributions = db.scalars(select(ReferralAttribution).where(
        ReferralAttribution.referrer_user_id == user.id)).all()
    attr_ids = [a.id for a in attributions]
    visits = db.scalar(select(func.count(ReferralEvent.id)).where(
        ReferralEvent.event_type == "link_opened",
        ReferralEvent.event_reference.like(f"{code_row.code}:%"))) or 0
    registrations = sum(1 for a in attributions if a.referred_user_id)
    verified = 0
    for a in attributions:
        if a.referred_user_id:
            u = db.get(User, a.referred_user_id)
            if u and u.email_verified:
                verified += 1
    by_status: dict[str, int] = {}
    for a in attributions:
        by_status[a.status] = by_status.get(a.status, 0) + 1
    return {
        "code": code_row.code,
        "link": referral_link(code_row.code),
        "link_visits_measured": visits,
        "registrations": registrations,
        "contact_verified": verified,
        "pending": by_status.get("pending", 0),
        "under_review": by_status.get("under_review", 0),
        "approved": by_status.get("approved", 0),
        "rejected": by_status.get("rejected", 0),
        "eligible": by_status.get("eligible", 0),
    }


def history_for_user(db: Session, user: User) -> dict:
    code_row = ensure_referral_code(db, user)
    attributions = db.scalars(select(ReferralAttribution).where(
        ReferralAttribution.referrer_user_id == user.id).order_by(
        ReferralAttribution.attributed_at.desc())).all()
    out = []
    for a in attributions:
        referred = db.get(User, a.referred_user_id) if a.referred_user_id else None
        events = db.scalars(select(ReferralEvent).where(
            ReferralEvent.attribution_id == a.id).order_by(ReferralEvent.created_at)).all()
        reward = db.scalars(select(ReferralReward).where(
            ReferralReward.attribution_id == a.id)).first()
        out.append({
            "id": a.id,
            "referred_name": referred.name if referred else None,
            "status": a.status,
            "source": a.attribution_source,
            "flag_reasons": [f for f in (a.flag_reasons or "").split(",") if f],
            "attributed_at": a.attributed_at.isoformat(),
            "events": [{"type": e.event_type, "at": e.created_at.isoformat(),
                        "verification": e.verification_status} for e in events],
            "reward": ({"type": reward.reward_type, "status": reward.status}
                       if reward else None),
        })
    code_events = db.scalars(select(ReferralEvent).where(
        ReferralEvent.attribution_id.is_(None),
        ReferralEvent.event_reference.like(f"{code_row.code}:%"),
        ReferralEvent.event_type.in_(["link_opened", "registration_started"]),
    ).order_by(ReferralEvent.created_at.desc())).all()
    return {
        "referrals": out,
        "pre_registration_events": [
            {"type": e.event_type, "at": e.created_at.isoformat()} for e in code_events
        ],
    }
