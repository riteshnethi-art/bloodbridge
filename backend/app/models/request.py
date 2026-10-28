"""Blood requests, candidate matches and permitted contact events."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

REQUEST_STATUSES = (
    "pending", "matching", "contact_initiated", "donor_responded",
    "fulfilled", "cancelled", "expired",
)

URGENCIES = ("critical", "urgent", "routine")

# From -> set of allowed transitions (state machine enforced server-side)
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"matching", "contact_initiated", "cancelled", "expired"},
    "matching": {"contact_initiated", "cancelled", "expired"},
    "contact_initiated": {"donor_responded", "fulfilled", "cancelled", "expired"},
    "donor_responded": {"fulfilled", "cancelled", "expired"},
    "fulfilled": {"fulfilled"},   # terminal
    "cancelled": {"cancelled"},   # terminal
    "expired": {"expired"},       # terminal
}


def can_transition(current: str, new: str) -> bool:
    return new in STATUS_TRANSITIONS.get(current, set())


class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    requester_name: Mapped[str] = mapped_column(String(120))
    contact_value: Mapped[str] = mapped_column(String(160))  # phone or email
    contact_method: Mapped[str] = mapped_column(String(20), default="phone")
    blood_group: Mapped[str] = mapped_column(String(4))
    city: Mapped[str] = mapped_column(String(120), index=True)
    locality: Mapped[str] = mapped_column(String(160), default="")
    hospital: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    units: Mapped[int] = mapped_column(Integer)
    urgency: Mapped[str] = mapped_column(String(20))
    needed_by: Mapped[datetime] = mapped_column(DateTime)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    closed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    matches: Mapped[list["Match"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("request_id", "donor_id", name="uq_request_donor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("blood_requests.id"), index=True)
    donor_id: Mapped[int] = mapped_column(ForeignKey("donors.id"), index=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    blood_compatible: Mapped[bool] = mapped_column(Boolean, default=True)
    exact_group: Mapped[bool] = mapped_column(Boolean, default=False)
    same_city: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    score_breakdown: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    request = relationship("BloodRequest", back_populates="matches")
    donor = relationship("Donor")


class ContactEvent(Base):
    __tablename__ = "contact_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("blood_requests.id"), index=True)
    donor_id: Mapped[int] = mapped_column(ForeignKey("donors.id"), index=True)
    initiated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    method: Mapped[str] = mapped_column(String(20), default="in_app")
    token: Mapped[str] = mapped_column(String(24), unique=True)  # platform-mediated reference
    status: Mapped[str] = mapped_column(String(20), default="initiated", index=True)
    donor_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    donor = relationship("Donor")
    request = relationship("BloodRequest")
