"""Blood request workflow service: creation, validation, status transitions."""
from __future__ import annotations

from datetime import timedelta, timezone

from sqlalchemy.orm import Session

from ..database import utcnow
from ..models.request import BloodRequest, can_transition
from ..models.user import User
from .audit import notify
from .geo import lookup_coords
from .matching import build_matches

MAX_UNITS = 20


class RequestValidationError(ValueError):
    pass


def validate_request_payload(data: dict) -> dict:
    """Server-side validation shared by the form API and the assistant."""
    errors: list[str] = []
    blood_group = (data.get("blood_group") or "").strip().upper()
    if blood_group not in ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"):
        errors.append("blood_group must be one of O-, O+, A-, A+, B-, B+, AB-, AB+")
    city = (data.get("city") or "").strip()
    if not (2 <= len(city) <= 120):
        errors.append("city is required (2-120 characters)")
    hospital = (data.get("hospital") or "").strip()
    if not (2 <= len(hospital) <= 200):
        errors.append("hospital is required (2-200 characters)")
    units = data.get("units")
    if not isinstance(units, int) or not (1 <= units <= MAX_UNITS):
        errors.append(f"units must be an integer between 1 and {MAX_UNITS}")
    urgency = (data.get("urgency") or "").strip().lower()
    if urgency not in ("critical", "urgent", "routine"):
        errors.append("urgency must be critical, urgent or routine")
    needed_by = data.get("needed_by")
    # Normalize: browsers send UTC ISO with 'Z' (tz-aware); the app stores naive
    # UTC (see database.utcnow). Compare likes with likes - never crash either way.
    if needed_by is not None and hasattr(needed_by, "tzinfo") and needed_by.tzinfo is not None:
        needed_by = needed_by.astimezone(timezone.utc).replace(tzinfo=None)
    now = utcnow()
    if not isinstance(needed_by, object) or not hasattr(needed_by, "timestamp"):
        errors.append("needed_by must be a date/time")
    else:
        if needed_by <= now:
            errors.append("needed_by must be in the future")
        elif needed_by > now + timedelta(days=90):
            errors.append("needed_by can be at most 90 days ahead")
    requester_name = (data.get("requester_name") or "").strip()
    if not (2 <= len(requester_name) <= 120):
        errors.append("requester_name is required")
    contact_value = (data.get("contact_value") or "").strip()
    if not (5 <= len(contact_value) <= 160):
        errors.append("contact_value (phone or email) is required")
    contact_method = (data.get("contact_method") or "phone").strip().lower()
    if contact_method not in ("phone", "email", "whatsapp"):
        errors.append("contact_method must be phone, email or whatsapp")
    if errors:
        raise RequestValidationError("; ".join(errors))
    return {
        "blood_group": blood_group,
        "city": city,
        "locality": (data.get("locality") or "").strip()[:160],
        "hospital": hospital,
        "units": units,
        "urgency": urgency,
        "needed_by": needed_by,
        "requester_name": requester_name,
        "contact_value": contact_value,
        "contact_method": contact_method,
        "notes": (data.get("notes") or "").strip()[:1000],
    }


def create_request(db: Session, payload: dict, user: User | None) -> BloodRequest:
    data = validate_request_payload(payload)
    coords = lookup_coords(data["city"], data["locality"])
    request = BloodRequest(
        public_id=_new_public_id(db),
        created_by=user.id if user else None,
        lat=coords[0] if coords else None,
        lng=coords[1] if coords else None,
        status="pending",
        **data,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    # Immediately attempt matching (workflow step 6-7).
    matches = build_matches(db, request)
    if matches and request.status == "pending":
        request.status = "matching"
        db.commit()
    if user:
        notify(db, user.id, "request_created", f"Request {request.public_id} submitted",
               f"Looking for potentially compatible {request.blood_group} donors near {request.city}.",
               link=f"/requests/{request.public_id}")
        db.commit()
    return request


def create_request_from_assistant(db: Session, proposal: dict, user: User | None) -> BloodRequest:
    payload = dict(proposal)
    from .assistant import URGENCY_LABELS  # noqa: F401  (labels are display-only)
    payload["needed_by"] = _parse_assistant_time(proposal["needed_by"])
    return create_request(db, payload, user)


def _parse_assistant_time(value: str):
    from datetime import datetime
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def _new_public_id(db: Session) -> str:
    import secrets
    while True:
        candidate = "BB-" + secrets.token_hex(4).upper()
        if not db.query(BloodRequest).filter(BloodRequest.public_id == candidate).first():
            return candidate


def transition_status(db: Session, request: BloodRequest, new_status: str,
                      actor: User, reason: str = "") -> BloodRequest:
    if new_status not in ("pending", "matching", "contact_initiated", "donor_responded",
                          "fulfilled", "cancelled", "expired"):
        raise RequestValidationError("Unknown status")
    if not can_transition(request.status, new_status):
        raise RequestValidationError(
            f"Invalid status transition: {request.status} -> {new_status}")
    if new_status in ("fulfilled", "cancelled") and not reason.strip():
        raise RequestValidationError(f"A reason is required to {new_status} a request")
    request.status = new_status
    if new_status in ("fulfilled", "cancelled", "expired"):
        request.closed_reason = reason or None
    else:
        request.closed_reason = None
    db.commit()
    if request.created_by:
        notify(db, request.created_by, "request_status",
               f"Request {request.public_id} is now {new_status.replace('_', ' ')}",
               reason or "", link=f"/requests/{request.public_id}")
        db.commit()
    return request


def expire_stale(db: Session, request: BloodRequest) -> None:
    if request.status in ("pending", "matching", "contact_initiated", "donor_responded"):
        if request.needed_by and request.needed_by < utcnow():
            request.status = "expired"
            request.closed_reason = "Needed-by window passed"
            db.commit()
