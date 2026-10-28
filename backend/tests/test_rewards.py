"""Rewards tests: eligibility, duplicate-claim prevention, inventory, education."""
from __future__ import annotations

import pytest

from app.database import SessionLocal, utcnow
from app.models.rewards import RewardOffer
from app.models.user import User
from app.security import hash_password
from app.services import rewards_service
from app.services.rewards_service import RewardError


def _user(db, email) -> User:
    user = User(name=email.split("@")[0].title(), email=email,
                password_hash=hash_password("passw0rd123"), email_verified=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _offer(db, quantity=5, status="active", **kwargs) -> RewardOffer:
    defaults = dict(
        offer_ref=f"OFF-T{abs(hash(str(kwargs.get('title', '')))) % 99999:05d}",
        partner_name="Demo Partner: TestCo", is_demo_partner=True,
        title=kwargs.get("title", "Test Offer"), description="d", category="general",
        quantity=quantity, remaining=quantity, valid_to=None, valid_from=None,
        redemption_instructions="Show code.", terms="Demo terms.", status=status,
    )
    defaults.update(kwargs)
    offer = RewardOffer(**defaults)
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


def test_claim_success_and_duplicate_prevention():
    db = SessionLocal()
    try:
        user = _user(db, "rw1@test.demo")
        offer = _offer(db, title=f"Claim Offer {utcnow().timestamp()}", quantity=2)
        claim = rewards_service.claim_offer(db, user.id, offer.id)
        assert claim.claim_code.startswith("CLM-")
        with pytest.raises(RewardError):
            rewards_service.claim_offer(db, user.id, offer.id)
        db.refresh(offer)
        assert offer.remaining == 1
    finally:
        db.close()


def test_inventory_exhaustion():
    db = SessionLocal()
    try:
        u1 = _user(db, "rw2@test.demo")
        u2 = _user(db, "rw3@test.demo")
        offer = _offer(db, title=f"Stock Offer {utcnow().timestamp()}", quantity=1)
        rewards_service.claim_offer(db, u1.id, offer.id)
        with pytest.raises(RewardError, match="run out"):
            rewards_service.claim_offer(db, u2.id, offer.id)
    finally:
        db.close()


def test_paused_and_expired_offers_rejected():
    db = SessionLocal()
    try:
        user = _user(db, "rw4@test.demo")
        paused = _offer(db, title=f"Paused {utcnow().timestamp()}", status="paused")
        with pytest.raises(RewardError, match="not active"):
            rewards_service.claim_offer(db, user.id, paused.id)
        expired = _offer(db, title=f"Expired {utcnow().timestamp()}",
                         valid_to=utcnow().replace(year=utcnow().year - 1))
        with pytest.raises(RewardError, match="expired"):
            rewards_service.claim_offer(db, user.id, expired.id)
    finally:
        db.close()


def test_education_modules_idempotent():
    db = SessionLocal()
    try:
        user = _user(db, "rw5@test.demo")
        record, created = rewards_service.complete_education_module(db, user.id, "donation_basics")
        assert created is True
        assert record.reference.startswith("REC-")
        again, created2 = rewards_service.complete_education_module(db, user.id, "donation_basics")
        assert created2 is False
        assert again.id == record.id
        with pytest.raises(RewardError):
            rewards_service.complete_education_module(db, user.id, "unknown_module")
    finally:
        db.close()


def test_wallet_payload_structure():
    db = SessionLocal()
    try:
        user = _user(db, "rw6@test.demo")
        rewards_service.complete_education_module(db, user.id, "compatibility_awareness")
        wallet = rewards_service.wallet_payload(db, user.id)
        assert len(wallet["education"]) == 1
        assert "education_modules_available" in wallet
        assert wallet["claims"] == []
    finally:
        db.close()
