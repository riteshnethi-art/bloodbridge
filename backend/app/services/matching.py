"""Candidate matching service.

Filters and ranks donors for a blood request:
1. Blood compatibility (hard filter, from services.compatibility).
2. Active, discoverable, contact-consenting donor profile.
3. Availability + freshness confirmation.
4. Geographic relevance (approx distance when coordinates exist, else city match).
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import utcnow
from ..models.donor import Donor
from ..models.request import BloodRequest, Match
from .compatibility import compatible_donor_groups
from .geo import haversine_km, lookup_coords


def _freshness_bonus(days: float) -> int:
    if days <= 1:
        return 5
    if days <= 7:
        return 3
    if days <= 30:
        return 1
    return 0


def _distance_score(distance_km: float | None, same_city: bool) -> int:
    if distance_km is None:
        return 12 if same_city else 0
    if distance_km <= 5:
        return 30
    if distance_km <= 15:
        return 25
    if distance_km <= 30:
        return 20
    if distance_km <= 60:
        return 15
    if distance_km <= 100:
        return 10
    return 5


def request_coords(request: BloodRequest) -> tuple[float, float] | None:
    if request.lat is not None and request.lng is not None:
        return (request.lat, request.lng)
    return lookup_coords(request.city, request.locality)


def build_matches(db: Session, request: BloodRequest, limit: int = 12) -> list[Match]:
    """Compute, persist and return candidate matches for a request."""
    donor_groups = compatible_donor_groups(request.blood_group)
    candidates = db.scalars(
        select(Donor).where(
            Donor.blood_group.in_(donor_groups),
            Donor.discoverable.is_(True),
            Donor.availability != "unavailable",
        )
    ).all()
    # Require a verified account (basic trust gate) but never expose personal data.
    donor_ids = [d.id for d in candidates if d.user.email_verified]
    if not donor_ids:
        db.query(Match).filter(Match.request_id == request.id).delete()
        db.commit()
        return []

    candidates = [d for d in candidates if d.id in set(donor_ids)]
    req_coords = request_coords(request)
    now = utcnow()

    results: list[tuple[float, Match]] = []
    for donor in candidates:
        distance: float | None = None
        if req_coords and donor.lat is not None and donor.lng is not None:
            distance = haversine_km(req_coords[0], req_coords[1], donor.lat, donor.lng)
        same_city = (donor.city or "").strip().lower() == (request.city or "").strip().lower()
        if distance is None and not same_city and req_coords is None:
            # Nothing geographically relevant is known - still allowed but low score.
            geo_component = 0
        else:
            geo_component = _distance_score(distance, same_city)

        exact = donor.blood_group == request.blood_group
        compat_component = 50 if exact else 40
        avail_component = 20 if donor.availability == "available" else 10
        confirmed_age = (now - (donor.last_confirmed_at or donor.created_at)).total_seconds() / 86400
        fresh_component = _freshness_bonus(confirmed_age)
        pref_component = 5 if (request.urgency in ("critical", "urgent") and donor.can_receive_urgent) else 2

        score = min(100.0, float(compat_component + geo_component + avail_component + fresh_component + pref_component))

        breakdown: dict[str, float | None] = {
            "compatibility": compat_component,
            "proximity": geo_component,
            "availability": avail_component,
            "freshness": fresh_component,
            "request_preferences": pref_component,
        }
        parts = [
            f"compatible blood group {donor.blood_group}" + (" (exact match)" if exact else ""),
        ]
        if distance is not None:
            parts.append(f"approx. {round(distance, 1)} km away")
        elif same_city:
            parts.append("same city (exact distance not available)")
        parts.append(f"availability: {donor.availability}")
        parts.append(f"availability confirmed {_freshness_label(confirmed_age)}")
        explanation = "Matched on: " + "; ".join(parts) + "."

        m = Match(
            request_id=request.id,
            donor_id=donor.id,
            distance_km=distance,
            blood_compatible=True,
            exact_group=exact,
            same_city=same_city,
            score=score,
            score_breakdown=json.dumps(breakdown),
            explanation=explanation,
        )
        results.append((score, m))

    db.query(Match).filter(Match.request_id == request.id).delete()
    results.sort(key=lambda t: (-t[0], t[1].distance_km if t[1].distance_km is not None else 1e9))
    matches = [m for _, m in results[:limit]]
    db.add_all(matches)
    db.commit()
    for m in matches:
        db.refresh(m)
    return matches


def _freshness_label(days: float) -> str:
    if days <= 1:
        return "within the last day"
    if days <= 7:
        return "within the last week"
    if days <= 30:
        return "within the last month"
    return "more than a month ago"


def should_run_matching(request: BloodRequest) -> bool:
    return request.status in ("pending", "matching")


def maybe_expire(db: Session, request: BloodRequest) -> None:
    """Lazily expire open requests whose needed-by date has passed."""
    if request.status in ("pending", "matching", "contact_initiated", "donor_responded"):
        if request.needed_by and request.needed_by < now_naive():
            request.status = "expired"
            request.closed_reason = "Needed-by window passed"
            db.commit()


def now_naive() -> datetime:
    return utcnow()
