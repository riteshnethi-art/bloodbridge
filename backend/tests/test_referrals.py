"""Referral program tests: codes, attribution, fraud guards, eligibility, limits."""
from __future__ import annotations

import pytest

from app.database import SessionLocal, utcnow
from app.models.referral import ReferralAttribution, ReferralCampaign, ReferralCode
from app.models.user import User
from app.security import hash_password
from app.services import referral_service
from app.services.referral_service import ReferralError


def _user(db, email, **kwargs) -> User:
    user = User(name=email.split("@")[0].title(), email=email,
                password_hash=hash_password("passw0rd123"),
                email_verified=True, onboarding_completed=False, **kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _campaign(db, **overrides) -> ReferralCampaign:
    from datetime import timedelta
    # End every pre-existing campaign so this test's campaign is the only active one.
    for existing in db.query(ReferralCampaign).all():
        existing.status = "ended"
    db.commit()
    defaults = dict(
        name="Test Campaign", start_at=utcnow() - timedelta(days=1),
        end_at=utcnow() + timedelta(days=30), eligible_event="onboarding_completed",
        reward_type="badge", per_user_limit=5, total_limit=100,
        auto_approve=True, requires_review=False, status="active",
    )
    defaults.update(overrides)
    campaign = ReferralCampaign(**defaults)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def test_code_format_and_uniqueness():
    db = SessionLocal()
    try:
        u1 = _user(db, "refa@test.demo")
        u2 = _user(db, "refb@test.demo")
        c1 = referral_service.ensure_referral_code(db, u1)
        c2 = referral_service.ensure_referral_code(db, u2)
        assert c1.code.startswith("BLOODBRIDGE-")
        assert len(c1.code) == len("BLOODBRIDGE-") + 5
        assert c1.code != c2.code
        assert referral_service.ensure_referral_code(db, u1).id == c1.id
        assert referral_service.referral_link(c1.code).startswith("http")
        assert "/join?ref=" in referral_service.referral_link(c1.code)
    finally:
        db.close()


def test_self_referral_blocked():
    db = SessionLocal()
    try:
        u = _user(db, "selfref@test.demo")
        code = referral_service.ensure_referral_code(db, u)
        with pytest.raises(ReferralError):
            referral_service.attribute(db, code.code, u)
    finally:
        db.close()


def test_one_referrer_per_account():
    db = SessionLocal()
    try:
        ref1 = _user(db, "refone@test.demo")
        ref2 = _user(db, "reftwo@test.demo")
        new = _user(db, "newbie@test.demo")
        c1 = referral_service.ensure_referral_code(db, ref1)
        c2 = referral_service.ensure_referral_code(db, ref2)
        a1 = referral_service.attribute(db, c1.code, new)
        assert a1.referrer_user_id == ref1.id
        a2 = referral_service.attribute(db, c2.code, new)
        assert a2.id == a1.id  # second code ignored, first referrer kept
    finally:
        db.close()


def test_identifier_overlap_flagged_not_auto_banned():
    db = SessionLocal()
    try:
        referrer = _user(db, "flagger@test.demo", phone="+911234567890")
        lookalike = _user(db, "flagger.suspect@test.demo", phone="+911234567890")
        code = referral_service.ensure_referral_code(db, referrer)
        attribution = referral_service.attribute(db, code.code, lookalike)
        assert "phone_matches_referrer" in attribution.flag_reasons
        assert attribution.status == "pending"
        # Onboarding with flags -> under_review, never auto-issued
        lookalike.onboarding_completed = True
        db.commit()
        result = referral_service.record_onboarding(db, lookalike)
        db.refresh(attribution)
        assert result["attributed"] is True
        assert attribution.status == "under_review"
    finally:
        db.close()


def test_reward_issued_after_onboarding_auto_approve():
    db = SessionLocal()
    try:
        _campaign(db, name="Auto Campaign")
        referrer = _user(db, "autoref@test.demo")
        new = _user(db, "autonew@test.demo")
        code = referral_service.ensure_referral_code(db, referrer)
        referral_service.attribute(db, code.code, new)
        new.onboarding_completed = True
        db.commit()
        result = referral_service.record_onboarding(db, new)
        assert result["reward"] == {"type": "badge", "status": "issued"}
        attribution = db.query(ReferralAttribution).filter(
            ReferralAttribution.referred_user_id == new.id).first()
        assert attribution.status == "approved"
    finally:
        db.close()


def test_requires_review_holds_for_admin():
    db = SessionLocal()
    try:
        campaign = _campaign(db, name="Review Campaign", auto_approve=False,
                             requires_review=True)
        admin = _user(db, "revadmin@test.demo", role="admin")
        referrer = _user(db, "revref@test.demo")
        new = _user(db, "revnew@test.demo")
        code = referral_service.ensure_referral_code(db, referrer)
        attribution = referral_service.attribute(db, code.code, new)
        new.onboarding_completed = True
        db.commit()
        referral_service.record_onboarding(db, new)
        db.refresh(attribution)
        assert attribution.status == "under_review"
        # Admin approves -> reward issued
        reviewed = referral_service.review_referral(db, attribution.id, True, "", admin)
        assert reviewed.status == "approved"
        assert campaign.times_issued == 1
    finally:
        db.close()


def test_rejection_requires_reason():
    db = SessionLocal()
    try:
        _campaign(db, name="Reject Campaign", auto_approve=False, requires_review=True)
        admin = _user(db, "rejadmin@test.demo", role="admin")
        referrer = _user(db, "rejref@test.demo")
        new = _user(db, "rejnew@test.demo")
        code = referral_service.ensure_referral_code(db, referrer)
        attribution = referral_service.attribute(db, code.code, new)
        new.onboarding_completed = True
        db.commit()
        referral_service.record_onboarding(db, new)
        with pytest.raises(ReferralError):
            referral_service.review_referral(db, attribution.id, False, "", admin)
        reviewed = referral_service.review_referral(db, attribution.id, False,
                                                    "duplicate account suspected", admin)
        assert reviewed.status == "rejected"
    finally:
        db.close()


def test_per_user_limit_enforced():
    db = SessionLocal()
    try:
        _campaign(db, name="Limit Campaign", per_user_limit=1)
        referrer = _user(db, "limitref@test.demo")
        code = referral_service.ensure_referral_code(db, referrer)
        for i in range(2):
            new = _user(db, f"limitnew{i}@test.demo")
            referral_service.attribute(db, code.code, new)
            new.onboarding_completed = True
            db.commit()
            referral_service.record_onboarding(db, new)
        rewards = db.query(ReferralAttribution).filter(
            ReferralAttribution.referrer_user_id == referrer.id).all()
        issued = sum(1 for a in rewards if a.status == "approved")
        assert issued == 1  # second referral hit the per-user limit
    finally:
        db.close()


def test_cash_reward_type_rejected():
    db = SessionLocal()
    try:
        _campaign(db, name="Cash Campaign", reward_type="cash")
        referrer = _user(db, "cashref@test.demo")
        new = _user(db, "cashnew@test.demo")
        code = referral_service.ensure_referral_code(db, referrer)
        attribution = referral_service.attribute(db, code.code, new)
        new.onboarding_completed = True
        db.commit()
        with pytest.raises(ReferralError):
            referral_service.record_onboarding(db, new)
    finally:
        db.close()


def test_stats_count_measurable_events():
    db = SessionLocal()
    try:
        referrer = _user(db, "statref@test.demo")
        code = referral_service.ensure_referral_code(db, referrer)
        referral_service.track_event(db, code.code, "link_opened")
        referral_service.track_event(db, code.code, "link_opened")  # idempotent
        referral_service.track_event(db, code.code, "registration_started")
        new = _user(db, "statnew@test.demo")
        referral_service.attribute(db, code.code, new)
        stats = referral_service.stats_for_user(db, referrer)
        assert stats["link_visits_measured"] == 2
        assert stats["registrations"] == 1
        assert stats["contact_verified"] == 1
    finally:
        db.close()
