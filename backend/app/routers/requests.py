"""Blood request management, matching and permitted contact."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..deps import get_current_user, require_user
from ..models.donor import Donor
from ..models.request import BloodRequest, ContactEvent, Match, can_transition
from ..models.user import User
from ..schemas import ContactIn, RequestIn, RespondIn, StatusIn
from ..serializers import contact_out, match_out, request_out
from ..services.audit import notify
from ..services.matching import build_matches
from ..services.request_service import (
    RequestValidationError, create_request, expire_stale, transition_status,
)

router = APIRouter(prefix="/api", tags=["requests"])


def _get_request(db: Session, public_id: str) -> BloodRequest:
    request = db.scalars(select(BloodRequest).where(
        BloodRequest.public_id == public_id)).first()
    if not request:
        raise HTTPException(404, "Request not found")
    expire_stale(db, request)
    return request


def _is_owner(request: BloodRequest, user: User | None) -> bool:
    if user is None:
        return request.created_by is None  # guest-created requests are demo-mode open
    return user.role == "admin" or request.created_by == user.id


@router.post("/requests")
def create_blood_request(data: RequestIn, db: Session = Depends(get_db),
                         user: User | None = Depends(get_current_user)):
    try:
        request = create_request(db, data.model_dump(), user)
    except RequestValidationError as exc:
        raise HTTPException(422, str(exc))
    matches = db.scalars(select(Match).where(Match.request_id == request.id)).all()
    return {
        "request": request_out(request, owner_view=True),
        "matches_found": len(matches),
        "matches_url": f"/api/requests/{request.public_id}/matches",
        "notice": ("BloodBridge does not guarantee that donors or blood will be found. "
                   "For emergencies contact your hospital or blood bank immediately."),
    }


@router.get("/requests")
def list_my_requests(scope: str = "mine", db: Session = Depends(get_db),
                     user: User = Depends(require_user)):
    if scope == "all":
        if user.role != "admin":
            raise HTTPException(403, "Administrator access required")
        requests = db.scalars(select(BloodRequest).order_by(
            BloodRequest.created_at.desc())).all()
    else:
        requests = db.scalars(select(BloodRequest).where(
            BloodRequest.created_by == user.id).order_by(
            BloodRequest.created_at.desc())).all()
    for r in requests:
        expire_stale(db, r)
    return {"requests": [request_out(r, owner_view=True) for r in requests]}


@router.get("/requests/{public_id}")
def get_request(public_id: str, db: Session = Depends(get_db),
                user: User | None = Depends(get_current_user)):
    request = _get_request(db, public_id)
    owner = _is_owner(request, user)
    return request_out(request, owner_view=owner)


@router.patch("/requests/{public_id}/status")
def update_status(public_id: str, data: StatusIn, db: Session = Depends(get_db),
                  user: User = Depends(require_user)):
    request = _get_request(db, public_id)
    if not _is_owner(request, user):
        raise HTTPException(403, "Only the request owner or an admin can update status")
    try:
        transition_status(db, request, data.status, user, reason=data.reason)
    except RequestValidationError as exc:
        raise HTTPException(422, str(exc))
    return request_out(request, owner_view=True)


@router.get("/requests/{public_id}/matches")
def get_matches(public_id: str, refresh: bool = False, db: Session = Depends(get_db),
                user: User | None = Depends(get_current_user)):
    request = _get_request(db, public_id)
    if not _is_owner(request, user):
        raise HTTPException(403, "Only the request owner or an admin can view matches")
    existing = db.scalars(select(Match).where(Match.request_id == request.id)).all()
    if refresh or (not existing and request.status in ("pending", "matching")):
        existing = build_matches(db, request)
        if existing and request.status == "pending":
            request.status = "matching"
            db.commit()
    matches = db.scalars(select(Match).where(Match.request_id == request.id)
                         .order_by(Match.score.desc())).all()
    return {
        "request": request_out(request, owner_view=_is_owner(request, user)),
        "matches": [match_out(m) for m in matches],
        "matching_explained": (
            "Candidates are filtered by blood compatibility, active profile, "
            "discoverability consent and availability, then ranked by proximity, "
            "availability freshness and request preferences. This is preliminary "
            "donor discovery - not medical clearance and not a guarantee."
        ),
        "no_match_guidance": (
            "If no donors appear: expand the search area, re-check nearer localities, "
            "or contact a hospital blood bank or regional blood centre - they maintain "
            "live inventory."
        ) if not matches else None,
    }


@router.get("/requests/{public_id}/contacts")
def request_contacts(public_id: str, db: Session = Depends(get_db),
                     user: User | None = Depends(get_current_user)):
    request = _get_request(db, public_id)
    if not _is_owner(request, user):
        raise HTTPException(403, "Only the request owner or an admin can view contact activity")
    events = db.scalars(select(ContactEvent).where(
        ContactEvent.request_id == request.id).order_by(ContactEvent.created_at.desc())).all()
    return {"contacts": [contact_out(e) for e in events]}


@router.post("/matches/{match_id}/contact")
def initiate_contact(match_id: int, data: ContactIn, db: Session = Depends(get_db),
                     user: User | None = Depends(get_current_user)):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    request = match.request
    if not _is_owner(request, user):
        raise HTTPException(403, "Only the request owner can initiate contact")
    if request.status not in ("pending", "matching"):
        raise HTTPException(422, f"Contact cannot be initiated from status '{request.status}'")

    donor = match.donor
    if donor.availability == "unavailable" or not donor.discoverable:
        raise HTTPException(422, "This donor is currently unavailable")

    method = data.method or "in_app"
    event = ContactEvent(
        match_id=match.id, request_id=request.id, donor_id=donor.id,
        initiated_by=user.id if user else None,
        method=method, token="CT-" + secrets.token_hex(5).upper(),
    )
    db.add(event)
    if can_transition(request.status, "contact_initiated"):
        request.status = "contact_initiated"
    db.commit()
    db.refresh(event)

    notify(db, donor.user_id, "contact_request",
           f"New {request.urgency} blood request: {request.blood_group} needed",
           f"{request.hospital}, {request.locality + ', ' if request.locality else ''}"
           f"{request.city} - needed by {request.needed_by.strftime('%d %b %Y %H:%M')}. "
           "Open your donor dashboard to accept or decline.",
           link="/dashboard/donor")
    db.commit()
    return {
        "contact": contact_out(event),
        "notice": ("A contact request was sent to the donor through BloodBridge. The "
                   "donor decides whether to respond - nothing is automatic, and the "
                   "donor's contact details stay private until they accept."),
    }


@router.get("/contacts/incoming")
def incoming_contacts(db: Session = Depends(get_db), user: User = Depends(require_user)):
    donor = db.scalars(select(Donor).where(Donor.user_id == user.id)).first()
    if not donor:
        raise HTTPException(404, "No donor profile")
    events = db.scalars(select(ContactEvent).where(
        ContactEvent.donor_id == donor.id).order_by(ContactEvent.created_at.desc())).all()
    return {"contacts": [contact_out(e, donor_view=True) for e in events]}


@router.post("/contacts/{event_id}/respond")
def respond_to_contact(event_id: int, data: RespondIn, db: Session = Depends(get_db),
                       user: User = Depends(require_user)):
    event = db.get(ContactEvent, event_id)
    if not event:
        raise HTTPException(404, "Contact request not found")
    donor = event.donor
    if donor.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Only the contacted donor can respond")
    if event.status != "initiated":
        raise HTTPException(422, f"This contact request was already {event.status}")

    event.status = "accepted" if data.accept else "declined"
    event.donor_message = data.message.strip()[:500]
    event.responded_at = utcnow()
    request = event.request
    if data.accept and can_transition(request.status, "donor_responded"):
        request.status = "donor_responded"
    db.commit()

    if data.accept:
        contact_line = "The donor chose in-app coordination."
        if donor.allow_direct_contact:
            u = donor.user
            contact_line = f"The donor agreed to share: {u.phone or u.email}"
        notify(db, request.created_by, "contact_accepted",
               f"A donor responded to request {request.public_id}",
               f"{contact_line} Remember: final eligibility is decided by donation "
               "professionals at the donation site.",
               link=f"/requests/{request.public_id}")
    else:
        notify(db, request.created_by, "contact_declined",
               f"A donor declined contact for {request.public_id}",
               "You can initiate contact with other potential donors from the matches page.",
               link=f"/requests/{request.public_id}")
    db.commit()
    return contact_out(event, donor_view=(donor.user_id == user.id))
