"""Donor profile. Never stores or exposes home address / exact precise coordinates
in any displayed data - coordinates are sensitive optional inputs used only to
compute approximate distances for matching."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

VALID_BLOOD_GROUPS = ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+")
VALID_AVAILABILITY = ("available", "maybe", "unavailable")
VALID_CONTACT_PREFS = ("in_app", "email", "phone", "whatsapp")


class Donor(Base):
    __tablename__ = "donors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    blood_group: Mapped[str] = mapped_column(String(4))
    city: Mapped[str] = mapped_column(String(120), index=True)
    locality: Mapped[str] = mapped_column(String(160), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferred_contact: Mapped[str] = mapped_column(String(20), default="in_app")
    availability: Mapped[str] = mapped_column(String(20), default="available")
    last_confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    discoverable: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_direct_contact: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Reveal phone/email only after the donor accepts a contact request",
    )
    can_receive_urgent: Mapped[bool] = mapped_column(Boolean, default=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
