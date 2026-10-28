"""Referral program ("BloodBridge Community Invites") models.

Design notes:
- ``ReferralAttribution.referred_user_id`` is nullable on purpose: ``link_opened``
  / ``registration_started`` events can be measured before we know who the
  visitor will become. The id is filled in when the account is created.
- Referral rewards are never cash. Reward types are limited to non-cash
  community recognition (defensively validated in the service layer).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

REFERRAL_EVENT_TYPES = (
    "link_opened", "registration_started", "account_created", "contact_verified",
    "onboarding_completed", "referral_reviewed", "eligible", "rejected",
)
ATTRIBUTION_STATUSES = ("pending", "under_review", "eligible", "approved", "rejected")
ATTRIBUTION_SOURCES = ("link", "invitation_message", "manual_entry", "assistant")
CAMPAIGN_STATUSES = ("draft", "pending_approval", "active", "paused", "ended")
REWARD_STATUSES = ("approved", "issued", "rejected")


class ReferralCode(Base):
    __tablename__ = "referral_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|paused|revoked
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReferralAttribution(Base):
    __tablename__ = "referral_attributions"
    __table_args__ = (
        UniqueConstraint("referral_code_id", "referred_user_id", name="uq_code_referred"),
        UniqueConstraint("referred_user_id", name="uq_one_referrer_per_referred"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    referral_code_id: Mapped[int] = mapped_column(ForeignKey("referral_codes.id"), index=True)
    attributed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    attribution_source: Mapped[str] = mapped_column(String(30), default="link")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    flag_reasons: Mapped[str] = mapped_column(Text, default="")  # comma-separated abuse flags


class ReferralEvent(Base):
    __tablename__ = "referral_events"
    __table_args__ = (UniqueConstraint("attribution_id", "event_type", "event_reference", name="uq_ref_event"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attribution_id: Mapped[int | None] = mapped_column(ForeignKey("referral_attributions.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    event_reference: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    verification_status: Mapped[str] = mapped_column(String(20), default="measured")  # measured|approximate


class ReferralCampaign(Base):
    __tablename__ = "referral_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    eligible_event: Mapped[str] = mapped_column(String(40), default="onboarding_completed")
    reward_type: Mapped[str] = mapped_column(String(30), default="badge")  # badge|certificate|educational (never cash)
    per_user_limit: Mapped[int] = mapped_column(Integer, default=10)  # max rewards per referrer
    total_limit: Mapped[int] = mapped_column(Integer, default=1000)   # overall campaign limit
    times_issued: Mapped[int] = mapped_column(Integer, default=0)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True)
    eligibility_rules: Mapped[str] = mapped_column(Text, default="")
    terms: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    approval_note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    __table_args__ = (UniqueConstraint("attribution_id", name="uq_reward_per_attribution"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attribution_id: Mapped[int] = mapped_column(ForeignKey("referral_attributions.id"), index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("referral_campaigns.id"), index=True)
    reward_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="approved", index=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text, default="")


class ReferralAuditLog(Base):
    __tablename__ = "referral_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    target_id: Mapped[str] = mapped_column(String(40), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
