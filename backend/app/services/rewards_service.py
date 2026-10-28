"""Community rewards service.

Rewards recognise community participation (verification, education, events,
onboarding, referral campaigns). They are NEVER conditional on donating blood,
promising to donate, responding to a request or recruiting donors - and never
cash. Limited-quantity claims are allocated inside a database transaction with
a uniqueness constraint preventing duplicate claims.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import utcnow
from ..models.rewards import RewardClaim, RewardOffer, RecognitionRecord
from .audit import log_reward_action, notify
from ..security import generate_code

FORBIDDEN_REWARD_TYPES = {"cash", "cashback", "money", "crypto", "payment", "points"}


class RewardError(ValueError):
    pass


EDUCATION_MODULES: dict[str, dict[str, str]] = {
    "donation_basics": {
        "title": "Blood Donation Basics",
        "description": "Learn how whole-blood donation works, common eligibility "
                       "considerations and what happens at a donation centre.",
    },
    "compatibility_awareness": {
        "title": "Compatibility Awareness",
        "description": "Understand why preliminary compatibility is only a discovery "
                       "aid and why crossmatching by professionals is essential.",
    },
    "safe_response_practices": {
        "title": "Safe Response Practices",
        "description": "How to respond to urgent requests respectfully, protect "
                       "privacy, and avoid pressure or misinformation.",
    },
}


def list_active_offers(db: Session) -> list[RewardOffer]:
    now = utcnow()
    offers = db.scalars(select(RewardOffer).where(RewardOffer.status == "active")).all()
    return [o for o in offers
            if (o.valid_from is None or o.valid_from <= now)
            and (o.valid_to is None or o.valid_to >= now)]


def claim_offer(db: Session, user_id: int, offer_id: int) -> RewardClaim:
    now = utcnow()
    # Transaction with row-level intent: re-read inside the transaction, check
    # inventory, decrement, and rely on the unique (offer, user) constraint.
    with db.begin_nested():
        offer = db.get(RewardOffer, offer_id)
        if offer is None:
            raise RewardError("Offer not found")
        if offer.status != "active":
            raise RewardError("This offer is not active")
        if offer.valid_from and offer.valid_from > now:
            raise RewardError("This offer is not yet valid")
        if offer.valid_to and offer.valid_to < now:
            raise RewardError("This offer has expired")
        existing = db.scalars(select(RewardClaim).where(
            RewardClaim.offer_id == offer_id, RewardClaim.user_id == user_id)).first()
        if existing:
            raise RewardError("You have already claimed this offer")
        if offer.remaining <= 0:
            raise RewardError("This offer has run out of quantity")
        offer.remaining -= 1
        claim = RewardClaim(offer_id=offer_id, user_id=user_id,
                            claim_code=generate_code(8, prefix="CLM-"))
        db.add(claim)
        try:
            db.flush()
        except IntegrityError:
            raise RewardError("You have already claimed this offer")
        log_reward_action(db, "offer_claimed", actor_id=user_id,
                          target_type="offer", target_id=offer.offer_ref)
        notify(db, user_id, "reward_claimed", f"Claimed: {offer.title}",
               f"Your claim reference is {claim.claim_code}. Show it to the partner "
               f"per the redemption instructions.", link="/rewards")
    db.commit()
    db.refresh(claim)
    return claim


def complete_education_module(db: Session, user_id: int, module_key: str) -> tuple[RecognitionRecord, bool]:
    """Idempotent: completing the same module twice returns the existing record."""
    module = EDUCATION_MODULES.get(module_key)
    if not module:
        raise RewardError("Unknown education module")
    existing = db.scalars(select(RecognitionRecord).where(
        RecognitionRecord.user_id == user_id,
        RecognitionRecord.source == "education",
        RecognitionRecord.meta_json.contains(module_key),
    )).first()
    if existing:
        return existing, False
    record = issue_recognition(
        db, user_id, kind="educational", title=module["title"],
        description=module["description"], source="education",
        meta={"module": module_key},
    )
    notify(db, user_id, "education_completed", f"Completed: {module['title']}",
           "Recognition added to your rewards wallet.", link="/rewards")
    db.commit()
    return record, True


def issue_recognition(db: Session, user_id: int, kind: str, title: str,
                      description: str, source: str, meta: dict | None = None) -> RecognitionRecord:
    if kind not in ("badge", "certificate", "educational"):
        raise RewardError("Invalid recognition kind")
    record = RecognitionRecord(
        user_id=user_id, kind=kind, title=title, description=description,
        reference=generate_code(10, prefix="REC-"), source=source,
        meta_json=json.dumps(meta or {}),
    )
    db.add(record)
    db.flush()
    log_reward_action(db, "recognition_issued", actor_id=None, target_type="recognition",
                      target_id=record.reference, reason=title)
    return record


def wallet_payload(db: Session, user_id: int) -> dict:
    recognitions = db.scalars(select(RecognitionRecord).where(
        RecognitionRecord.user_id == user_id).order_by(RecognitionRecord.issued_at.desc())).all()
    claims = db.scalars(select(RewardClaim).where(
        RewardClaim.user_id == user_id).order_by(RewardClaim.claimed_at.desc())).all()
    offers = {o.id: o for o in db.scalars(select(RewardOffer)).all()}
    now = utcnow()
    claimed_items = []
    for c in claims:
        offer = offers.get(c.offer_id)
        if not offer:
            continue
        status = c.status
        if status == "claimed" and offer.valid_to and offer.valid_to < now:
            status = "expired"
        claimed_items.append({
            "claim_code": c.claim_code,
            "status": status,
            "claimed_at": c.claimed_at.isoformat(),
            "redeemed_at": c.redeemed_at.isoformat() if c.redeemed_at else None,
            "offer": {
                "offer_ref": offer.offer_ref,
                "title": offer.title,
                "partner_name": offer.partner_name,
                "is_demo_partner": offer.is_demo_partner,
                "terms": offer.terms,
                "redemption_instructions": offer.redemption_instructions,
            },
        })
    return {
        "badges": [r for r in recognitions if r.kind == "badge"],
        "certificates": [r for r in recognitions if r.kind == "certificate"],
        "education": [r for r in recognitions if r.kind == "educational"],
        "claims": claimed_items,
        "education_modules_available": [
            {"key": k, **m} for k, m in EDUCATION_MODULES.items()
        ],
    }


def redeem_claim(db: Session, claim_code: str, actor_id: int) -> RewardClaim:
    claim = db.scalars(select(RewardClaim).where(RewardClaim.claim_code == claim_code)).first()
    if not claim:
        raise RewardError("Claim not found")
    if claim.status != "claimed":
        raise RewardError(f"Claim is {claim.status}, cannot redeem")
    claim.status = "redeemed"
    claim.redeemed_at = utcnow()
    log_reward_action(db, "claim_redeemed", actor_id=actor_id,
                      target_type="claim", target_id=claim_code)
    db.commit()
    return claim
