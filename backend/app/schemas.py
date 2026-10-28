"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

BloodGroup = Literal["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
Urgency = Literal["critical", "urgent", "routine"]


class ORMDict(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=32)
    role: Literal["requester", "donor"] = "requester"
    referral_code: Optional[str] = Field(default=None, max_length=32)
    privacy_accepted: bool = True

    @field_validator("privacy_accepted")
    @classmethod
    def must_accept_privacy(cls, v: bool) -> bool:
        if not v:
            raise ValueError("The privacy notice must be accepted to register")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORMDict):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    role: str
    email_verified: bool
    onboarding_completed: bool
    created_at: datetime


class AuthOut(BaseModel):
    token: str
    user: UserOut
    demo_notice: str = ("Demo mode: contact verification is simulated. Production "
                        "deployments must verify email/phone before enabling "
                        "sensitive actions.")


# ---------------------------------------------------------------- donors

class DonorIn(BaseModel):
    blood_group: BloodGroup
    city: str = Field(min_length=2, max_length=120)
    locality: str = Field(default="", max_length=160)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    preferred_contact: Literal["in_app", "email", "phone", "whatsapp"] = "in_app"
    availability: Literal["available", "maybe", "unavailable"] = "available"
    discoverable: bool = True
    allow_direct_contact: bool = False
    can_receive_urgent: bool = True


class DonorOut(ORMDict):
    id: int
    user_id: int
    blood_group: str
    city: str
    locality: str
    preferred_contact: str
    availability: str
    last_confirmed_at: datetime
    discoverable: bool
    allow_direct_contact: bool
    can_receive_urgent: bool
    verified: bool
    created_at: datetime


class DonorAdminOut(DonorOut):
    """Admin-only view (still avoids full addresses; shows masked contact)."""
    masked_contact: str = ""


class AvailabilityIn(BaseModel):
    availability: Literal["available", "maybe", "unavailable"]


# ---------------------------------------------------------------- requests

class RequestIn(BaseModel):
    blood_group: BloodGroup
    city: str = Field(min_length=2, max_length=120)
    locality: str = Field(default="", max_length=160)
    hospital: str = Field(min_length=2, max_length=200)
    units: int = Field(ge=1, le=20)
    urgency: Urgency
    needed_by: datetime
    requester_name: str = Field(min_length=2, max_length=120)
    contact_value: str = Field(min_length=5, max_length=160)
    contact_method: Literal["phone", "email", "whatsapp"] = "phone"
    notes: str = Field(default="", max_length=1000)


class StatusIn(BaseModel):
    status: Literal["pending", "matching", "contact_initiated", "donor_responded",
                    "fulfilled", "cancelled", "expired"]
    reason: str = Field(default="", max_length=500)


class ContactIn(BaseModel):
    method: Optional[Literal["in_app", "email", "phone", "whatsapp"]] = None


class RespondIn(BaseModel):
    accept: bool
    message: str = Field(default="", max_length=500)


# ---------------------------------------------------------------- assistant

class AssistantMessageIn(BaseModel):
    session_id: str = Field(min_length=6, max_length=64)
    message: str = Field(min_length=1, max_length=2000)


# ---------------------------------------------------------------- rewards

class EducationIn(BaseModel):
    module_key: str = Field(min_length=2, max_length=60)


class OfferIn(BaseModel):
    partner_name: str = Field(min_length=2, max_length=160)
    is_demo_partner: bool = True
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="general", max_length=60)
    eligibility_rules: str = Field(default="", max_length=1000)
    quantity: int = Field(ge=0, le=100000)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    redemption_instructions: str = Field(default="", max_length=1000)
    terms: str = Field(default="", max_length=2000)
    status: Literal["draft", "active", "paused", "expired"] = "active"


class OfferPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[Literal["draft", "active", "paused", "expired"]] = None
    quantity: Optional[int] = Field(default=None, ge=0, le=100000)


# ---------------------------------------------------------------- referrals

class AttributeIn(BaseModel):
    code: str = Field(min_length=6, max_length=32)
    source: Literal["link", "invitation_message", "manual_entry", "assistant"] = "link"


class TrackIn(BaseModel):
    code: str = Field(min_length=6, max_length=32)
    event_type: Literal["link_opened", "registration_started"]
    reference: Optional[str] = Field(default=None, max_length=60)


class CampaignIn(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=2000)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    eligible_event: Literal["onboarding_completed", "contact_verified"] = "onboarding_completed"
    reward_type: Literal["badge", "certificate", "educational"] = "badge"
    per_user_limit: int = Field(default=10, ge=1, le=1000)
    total_limit: int = Field(default=1000, ge=1, le=1000000)
    auto_approve: bool = False
    requires_review: bool = True
    eligibility_rules: str = Field(default="", max_length=2000)
    terms: str = Field(default="", max_length=4000)


class CampaignPatch(BaseModel):
    status: Optional[Literal["draft", "pending_approval", "active", "paused", "ended"]] = None
    approval_note: Optional[str] = Field(default=None, max_length=1000)
    per_user_limit: Optional[int] = Field(default=None, ge=1, le=1000)
    total_limit: Optional[int] = Field(default=None, ge=1, le=1000000)
    end_at: Optional[datetime] = None


class ReviewIn(BaseModel):
    approve: bool
    reason: str = Field(default="", max_length=500)
