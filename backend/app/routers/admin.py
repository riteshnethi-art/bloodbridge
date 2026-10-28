"""Administrator endpoints. Every route requires the admin role server-side."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models.donor import Donor
from ..models.misc import Notification
from ..models.referral import (
    ReferralAttribution, ReferralAuditLog, ReferralCampaign, ReferralCode,
    ReferralReward,
)
from ..models.rewards import RewardAuditLog, RewardClaim, RewardOffer
from ..models.request import BloodRequest, ContactEvent
from ..models.user import User
from ..schemas import CampaignIn, CampaignPatch, OfferIn, OfferPatch, ReviewIn
from ..serializers import offer_out, request_out
from ..services import referral_service, rewards_service
from ..services.audit import log_referral_action, log_reward_action, notify
from ..services.rewards_service import RewardError
from ..services.referral_service import ReferralError

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    users_total = db.scalar(select(func.count(User.id))) or 0
    donors_total = db.scalar(select(func.count(Donor.id))) or 0
    requests_by_status = dict(db.execute(
        select(BloodRequest.status, func.count(BloodRequest.id)).group_by(BloodRequest.status)
    ).all())
    claims_total = db.scalar(select(func.count(RewardClaim.id))) or 0
    offers_active = db.scalar(select(func.count(RewardOffer.id)).where(
        RewardOffer.status == "active")) or 0
    referrals = dict(db.execute(
        select(ReferralAttribution.status, func.count(ReferralAttribution.id))
        .group_by(ReferralAttribution.status)).all())
    flagged = db.scalar(select(func.count(ReferralAttribution.id)).where(
        ReferralAttribution.flag_reasons != "")) or 0
    contacts = db.scalar(select(func.count(ContactEvent.id))) or 0
    return {
        "users": {"total": users_total, "donors": donors_total},
        "requests_by_status": requests_by_status,
        "reward_claims": claims_total,
        "active_offers": offers_active,
        "referrals_by_status": referrals,
        "flagged_referrals": flagged,
        "contact_events": contacts,
    }


@router.get("/users")
def users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(select(User).order_by(User.created_at.desc())).all()
    out = []
    for u in rows:
        out.append({
            "id": u.id, "name": u.name, "email": u.email,
            "role": u.role, "email_verified": u.email_verified,
            "onboarding_completed": u.onboarding_completed,
            "created_at": u.created_at.isoformat(),
        })
    return {"users": out}


@router.get("/requests")
def all_requests(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(select(BloodRequest).order_by(BloodRequest.created_at.desc())).all()
    return {"requests": [request_out(r, owner_view=True) for r in rows]}


@router.post("/donors/{donor_id}/verify")
def verify_donor(donor_id: int, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)):
    donor = db.get(Donor, donor_id)
    if not donor:
        raise HTTPException(404, "Donor not found")
    if donor.verified:
        return {"verified": True, "already_verified": True}
    donor.verified = True
    rewards_service.issue_recognition(
        db, donor.user_id, kind="badge", title="Verified Donor Profile",
        description="Completed donor profile verification review by a BloodBridge "
                    "administrator. Verification is an account-trust signal only - "
                    "it is not medical eligibility.",
        source="profile_verification", meta={"donor_id": donor.id},
    )
    notify(db, donor.user_id, "verified", "Your donor profile is verified",
           "A 'Verified Donor Profile' badge was added to your rewards wallet.",
           link="/rewards")
    log_reward_action(db, "donor_verified", actor_id=admin.id,
                      target_type="donor", target_id=str(donor.id))
    db.commit()
    return {"verified": True, "already_verified": False}


# ---------------------------------------------------------------- offers

@router.get("/offers")
def admin_offers(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(select(RewardOffer).order_by(RewardOffer.created_at.desc())).all()
    return {"offers": [offer_out(o) for o in rows]}


@router.post("/offers")
def create_offer(data: OfferIn, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)):
    import secrets
    offer = RewardOffer(
        offer_ref="OFF-" + secrets.token_hex(4).upper(),
        created_by=admin.id,
        remaining=data.quantity,
        **data.model_dump(),
    )
    db.add(offer)
    log_reward_action(db, "offer_created", actor_id=admin.id,
                      target_type="offer", target_id=offer.offer_ref,
                      reason=f"status={offer.status}")
    db.commit()
    db.refresh(offer)
    return offer_out(offer)


@router.patch("/offers/{offer_id}")
def patch_offer(offer_id: int, data: OfferPatch, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    offer = db.get(RewardOffer, offer_id)
    if not offer:
        raise HTTPException(404, "Offer not found")
    changes = data.model_dump(exclude_none=True)
    if "quantity" in changes:
        claimed = db.scalar(select(func.count(RewardClaim.id)).where(
            RewardClaim.offer_id == offer.id)) or 0
        if changes["quantity"] < claimed:
            raise HTTPException(422, f"Quantity cannot be below already-claimed count ({claimed})")
        offer.quantity = changes.pop("quantity")
        offer.remaining = max(0, offer.quantity - claimed)
    for key, value in changes.items():
        setattr(offer, key, value)
    log_reward_action(db, "offer_updated", actor_id=admin.id,
                      target_type="offer", target_id=offer.offer_ref,
                      reason=",".join(changes.keys()))
    db.commit()
    return offer_out(offer)


@router.post("/claims/{claim_code}/redeem")
def redeem(claim_code: str, db: Session = Depends(get_db),
           admin: User = Depends(require_admin)):
    try:
        claim = rewards_service.redeem_claim(db, claim_code, admin.id)
    except RewardError as exc:
        raise HTTPException(422, str(exc))
    return {"claim_code": claim.claim_code, "status": claim.status,
            "redeemed_at": claim.redeemed_at.isoformat()}


# ---------------------------------------------------------------- referrals

@router.get("/referrals")
def admin_referrals(status: str | None = None, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    query = select(ReferralAttribution).order_by(ReferralAttribution.attributed_at.desc())
    if status:
        query = query.where(ReferralAttribution.status == status)
    rows = db.scalars(query).all()
    out = []
    for a in rows:
        referrer = db.get(User, a.referrer_user_id)
        referred = db.get(User, a.referred_user_id) if a.referred_user_id else None
        reward = db.scalars(select(ReferralReward).where(
            ReferralReward.attribution_id == a.id)).first()
        out.append({
            "id": a.id,
            "referrer": {"id": referrer.id, "name": referrer.name, "email": referrer.email} if referrer else None,
            "referred": {"id": referred.id, "name": referred.name, "email": referred.email} if referred else None,
            "status": a.status,
            "source": a.attribution_source,
            "flag_reasons": [f for f in (a.flag_reasons or "").split(",") if f],
            "attributed_at": a.attributed_at.isoformat(),
            "reward": ({"type": reward.reward_type, "status": reward.status} if reward else None),
        })
    return {"referrals": out}


@router.post("/referrals/{attribution_id}/review")
def review(attribution_id: int, data: ReviewIn, db: Session = Depends(get_db),
           admin: User = Depends(require_admin)):
    try:
        attribution = referral_service.review_referral(
            db, attribution_id, data.approve, data.reason, admin)
    except ReferralError as exc:
        raise HTTPException(422, str(exc))
    return {"id": attribution.id, "status": attribution.status}


@router.get("/referrals/campaigns")
def campaigns(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(select(ReferralCampaign).order_by(
        ReferralCampaign.created_at.desc())).all()
    return {"campaigns": [_campaign_admin_out(c) for c in rows]}


def _campaign_admin_out(c: ReferralCampaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "start_at": c.start_at.isoformat() if c.start_at else None,
        "end_at": c.end_at.isoformat() if c.end_at else None,
        "eligible_event": c.eligible_event,
        "reward_type": c.reward_type,
        "per_user_limit": c.per_user_limit,
        "total_limit": c.total_limit,
        "times_issued": c.times_issued,
        "auto_approve": c.auto_approve,
        "requires_review": c.requires_review,
        "eligibility_rules": c.eligibility_rules,
        "terms": c.terms,
        "status": c.status,
        "approval_note": c.approval_note,
        "created_at": c.created_at.isoformat(),
    }


@router.post("/referrals/campaigns")
def create_campaign(data: CampaignIn, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    campaign = ReferralCampaign(created_by=admin.id, **data.model_dump())
    # Administrator-created campaigns start in pending_approval and must be
    # explicitly activated (approval requirement from the spec).
    campaign.status = "pending_approval"
    db.add(campaign)
    log_referral_action(db, "campaign_created", actor_id=admin.id,
                        target_id=str(campaign.id), reason=campaign.name)
    db.commit()
    db.refresh(campaign)
    return _campaign_admin_out(campaign)


@router.patch("/referrals/campaigns/{campaign_id}")
def patch_campaign(campaign_id: int, data: CampaignPatch, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    campaign = db.get(ReferralCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    changes = data.model_dump(exclude_none=True)
    new_status = changes.pop("status", None)
    if new_status and new_status == "active" and campaign.status not in ("active", "paused", "ended"):
        # Activation requires an explicit approval note (compliance review gate).
        note = changes.pop("approval_note", None) or campaign.approval_note
        if not note or not note.strip():
            raise HTTPException(422, "Activating a campaign requires an approval note "
                                      "(compliance review must be recorded)")
        campaign.approval_note = note
    for key, value in changes.items():
        setattr(campaign, key, value)
    if new_status:
        campaign.status = new_status
        log_referral_action(db, f"campaign_{new_status}", actor_id=admin.id,
                            target_id=str(campaign.id), reason=campaign.approval_note or "")
    db.commit()
    db.refresh(campaign)
    return _campaign_admin_out(campaign)


@router.get("/referrals/campaigns/{campaign_id}/export")
def export_campaign(campaign_id: int, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    campaign = db.get(ReferralCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    rows = db.scalars(select(ReferralAttribution).order_by(
        ReferralAttribution.attributed_at)).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["attribution_id", "referrer_id", "referred_id", "status",
                     "source", "flag_reasons", "attributed_at", "reward_status"])
    for a in rows:
        reward = db.scalars(select(ReferralReward).where(
            ReferralReward.attribution_id == a.id,
            ReferralReward.campaign_id == campaign.id)).first()
        writer.writerow([a.id, a.referrer_user_id, a.referred_user_id, a.status,
                         a.attribution_source, a.flag_reasons,
                         a.attributed_at.isoformat(),
                         reward.status if reward else ""])
    filename = f"campaign-{campaign.id}-stats.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------- audit logs

@router.get("/audit/rewards")
def audit_rewards(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(select(RewardAuditLog).order_by(
        RewardAuditLog.timestamp.desc()).limit(200)).all()
    return {"logs": [{
        "id": r.id, "actor_id": r.actor_id, "action": r.action,
        "target_type": r.target_type, "target_id": r.target_id,
        "reason": r.reason, "timestamp": r.timestamp.isoformat(),
    } for r in rows]}


@router.get("/audit/referrals")
def audit_referrals(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(select(ReferralAuditLog).order_by(
        ReferralAuditLog.timestamp.desc()).limit(200)).all()
    return {"logs": [{
        "id": r.id, "actor_id": r.actor_id, "action": r.action,
        "target_id": r.target_id, "reason": r.reason,
        "timestamp": r.timestamp.isoformat(),
    } for r in rows]}
