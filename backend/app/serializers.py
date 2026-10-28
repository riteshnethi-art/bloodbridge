"""Response serializers. Donor privacy is enforced here:
no phone numbers, no exact coordinates, no full addresses in donor-facing data."""
from __future__ import annotations

from .models.donor import Donor
from .models.misc import Notification
from .models.request import BloodRequest, ContactEvent, Match
from .models.rewards import RewardOffer, RecognitionRecord


def donor_public(donor: Donor, distance_km: float | None = None) -> dict:
    return {
        "donor_id": donor.id,
        "blood_group": donor.blood_group,
        "city": donor.city,
        "locality": donor.locality,
        "approx_distance_km": round(distance_km, 1) if distance_km is not None else None,
        "availability": donor.availability,
        "last_confirmed_at": donor.last_confirmed_at.isoformat() if donor.last_confirmed_at else None,
        "verified": donor.verified,
        "preferred_contact": donor.preferred_contact,
        "can_receive_urgent": donor.can_receive_urgent,
    }


def match_out(match: Match) -> dict:
    donor = match.donor
    return {
        "id": match.id,
        "request_id": match.request_id,
        "donor": donor_public(donor, match.distance_km),
        "exact_group": match.exact_group,
        "same_city": match.same_city,
        "score": round(match.score, 1),
        "score_breakdown": match.score_breakdown,
        "explanation": match.explanation,
        "created_at": match.created_at.isoformat(),
    }


def request_out(request: BloodRequest, *, owner_view: bool = False) -> dict:
    base = {
        "public_id": request.public_id,
        "blood_group": request.blood_group,
        "city": request.city,
        "locality": request.locality,
        "hospital": request.hospital,
        "units": request.units,
        "urgency": request.urgency,
        "needed_by": request.needed_by.isoformat(),
        "status": request.status,
        "notes": request.notes,
        "created_at": request.created_at.isoformat(),
        "closed_reason": request.closed_reason,
        "compatibility_notice": (
            "Matching supports preliminary donor discovery only. Compatibility and "
            "donor eligibility must be assessed by qualified healthcare professionals."
        ),
    }
    if owner_view:
        base.update({
            "requester_name": request.requester_name,
            "contact_method": request.contact_method,
            "contact_value": request.contact_value,
            "created_by": request.created_by,
        })
    else:
        # Public tracking view: hide the requester's contact details.
        base["requester_name"] = request.requester_name.split(" ")[0] + " " + (request.requester_name.split(" ")[1][:1] + "." if len(request.requester_name.split(" ")) > 1 else "")
    return base


def contact_out(event: ContactEvent, *, donor_view: bool = False) -> dict:
    data = {
        "id": event.id,
        "request_public_id": event.request.public_id,
        "method": event.method,
        "status": event.status,
        "token": event.token,
        "donor_message": event.donor_message if event.status in ("accepted", "declined") else "",
        "created_at": event.created_at.isoformat(),
        "responded_at": event.responded_at.isoformat() if event.responded_at else None,
        "blood_group": event.request.blood_group,
        "city": event.request.city,
        "locality": event.request.locality,
        "hospital": event.request.hospital,
        "urgency": event.request.urgency,
        "needed_by": event.request.needed_by.isoformat(),
        "units": event.request.units,
    }
    if donor_view:
        requester = event.request
        data["requester_name"] = requester.requester_name
        data["requester_contact"] = requester.contact_value
        data["requester_contact_method"] = requester.contact_method
    else:
        donor = event.donor
        data["donor"] = donor_public(donor)
        if event.status == "accepted":
            data["donor_contact_revealed"] = bool(donor.allow_direct_contact)
            if donor.allow_direct_contact:
                # Revealed only because the donor accepted this specific request
                data["donor_contact"] = donor.user.phone or donor.user.email
    return data


def offer_out(offer: RewardOffer) -> dict:
    return {
        "id": offer.id,
        "offer_ref": offer.offer_ref,
        "partner_name": offer.partner_name,
        "is_demo_partner": offer.is_demo_partner,
        "partner_label": "Demo Partner (not a real business)" if offer.is_demo_partner else "Verified Partner",
        "title": offer.title,
        "description": offer.description,
        "category": offer.category,
        "eligibility_rules": offer.eligibility_rules,
        "quantity": offer.quantity,
        "remaining": offer.remaining,
        "valid_from": offer.valid_from.isoformat() if offer.valid_from else None,
        "valid_to": offer.valid_to.isoformat() if offer.valid_to else None,
        "redemption_instructions": offer.redemption_instructions,
        "terms": offer.terms,
        "status": offer.status,
    }


def recognition_out(record: RecognitionRecord) -> dict:
    return {
        "id": record.id,
        "kind": record.kind,
        "title": record.title,
        "description": record.description,
        "reference": record.reference,
        "source": record.source,
        "issued_at": record.issued_at.isoformat(),
    }


def notification_out(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.ntype,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "read": n.read,
        "created_at": n.created_at.isoformat(),
    }
