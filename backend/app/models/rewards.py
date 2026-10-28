"""Community rewards: offers, claims, recognition, audit.

Rewards recognize community participation (verification, education, events,
referral campaigns). They are never conditional on donating blood.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

OFFER_STATUSES = ("draft", "active", "paused", "expired")
CLAIM_STATUSES = ("claimed", "redeemed", "revoked")
RECOGNITION_KINDS = ("badge", "certificate", "educational")
RECOGNITION_SOURCES = ("profile_verification", "education", "community_event", "referral_campaign", "onboarding")


class RewardOffer(Base):
    __tablename__ = "reward_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_ref: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    partner_name: Mapped[str] = mapped_column(String(160))
    is_demo_partner: Mapped[bool] = mapped_column(default=True)  # never pass demo partners off as real
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="general")
    eligibility_rules: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    remaining: Mapped[int] = mapped_column(Integer, default=0)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    redemption_instructions: Mapped[str] = mapped_column(Text, default="")
    terms: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RewardClaim(Base):
    __tablename__ = "reward_claims"
    __table_args__ = (UniqueConstraint("offer_id", "user_id", name="uq_offer_user_claim"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("reward_offers.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    claim_code: Mapped[str] = mapped_column(String(24), unique=True)  # secure claim reference
    status: Mapped[str] = mapped_column(String(20), default="claimed", index=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RecognitionRecord(Base):
    __tablename__ = "recognition_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # badge | certificate | educational
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    reference: Mapped[str] = mapped_column(String(24), unique=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RewardAuditLog(Base):
    __tablename__ = "reward_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    target_type: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[str] = mapped_column(String(40), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
