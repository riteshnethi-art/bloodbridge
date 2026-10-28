"""Matching service tests: filtering, ranking, honesty about unknown distances.

Each test uses a unique city prefix so committed demo rows from other tests
cannot interfere (the test DB is shared within the session).
"""
from __future__ import annotations

from datetime import timedelta

from app.database import SessionLocal, utcnow
from app.models.donor import Donor
from app.models.request import Match
from app.models.user import User
from app.security import hash_password
from app.services.matching import build_matches
from app.services.request_service import create_request


def _make_donor(db, email, group, city, locality, availability="available",
                discoverable=True, lat=None, lng=None, confirmed_hours_ago=1):
    user = User(name=email.split("@")[0].title(), email=email,
                password_hash=hash_password("passw0rd123"), role="donor",
                email_verified=True)
    db.add(user)
    db.flush()
    donor = Donor(user_id=user.id, blood_group=group, city=city, locality=locality,
                  lat=lat, lng=lng, availability=availability,
                  last_confirmed_at=utcnow() - timedelta(hours=confirmed_hours_ago),
                  discoverable=discoverable)
    db.add(donor)
    db.commit()
    db.refresh(donor)
    return donor


def _request(db, group="O-", city="Zcity", locality="Zarea", urgency="urgent",
             lat=None, lng=None):
    request = create_request(db, {
        "blood_group": group, "city": city, "locality": locality,
        "hospital": "Test Hospital", "units": 1, "urgency": urgency,
        "needed_by": utcnow() + timedelta(days=1),
        "requester_name": "Test Requester", "contact_value": "+919999900000",
        "contact_method": "phone", "notes": "",
    }, None)
    if lat is not None:
        request.lat, request.lng = lat, lng
        db.commit()
    return request


def test_only_compatible_donors_matched():
    db = SessionLocal()
    try:
        _make_donor(db, "m1@test.demo", "O-", "ZcityA", "ZareaA")
        _make_donor(db, "m2@test.demo", "AB+", "ZcityA", "ZareaA")
        request = _request(db, group="O-", city="ZcityA", locality="ZareaA")
        matches = build_matches(db, request)
        groups = {m.donor.blood_group for m in matches}
        assert groups == {"O-"}
    finally:
        db.close()


def test_undiscoverable_and_unavailable_excluded():
    db = SessionLocal()
    try:
        hidden = _make_donor(db, "m3@test.demo", "O-", "ZcityB", "ZareaB", discoverable=False)
        unavailable = _make_donor(db, "m4@test.demo", "O-", "ZcityB", "ZareaB",
                                  availability="unavailable")
        visible = _make_donor(db, "m5@test.demo", "O-", "ZcityB", "ZareaB")
        request = _request(db, city="ZcityB", locality="ZareaB")
        matches = build_matches(db, request)
        donor_ids = {m.donor_id for m in matches}
        assert visible.id in donor_ids
        assert hidden.id not in donor_ids
        assert unavailable.id not in donor_ids
    finally:
        db.close()


def test_proximity_ranking_with_coordinates():
    db = SessionLocal()
    try:
        near = _make_donor(db, "near@test.demo", "O-", "ZcityC", "ZareaC",
                           lat=17.4401, lng=78.3486)
        far = _make_donor(db, "far@test.demo", "O-", "ZcityFar", "ZareaFar",
                          lat=28.5921, lng=77.0460)
        request = _request(db, city="ZcityC", locality="ZareaC", lat=17.44, lng=78.35)
        matches = build_matches(db, request)
        by_donor = {m.donor_id: m for m in matches}
        assert by_donor[near.id].distance_km is not None
        assert by_donor[near.id].distance_km < 2
        assert by_donor[far.id].distance_km > 1000
        assert by_donor[near.id].score > by_donor[far.id].score
        assert "km" in by_donor[near.id].explanation
    finally:
        db.close()


def test_no_invented_distance_when_coords_missing():
    db = SessionLocal()
    try:
        donor = _make_donor(db, "nocoords@test.demo", "O-", "ZcityD", "ZareaD",
                            lat=None, lng=None)
        request = _request(db, city="ZcityD", locality="ZareaD", lat=None, lng=None)
        matches = build_matches(db, request)
        match = next(m for m in matches if m.donor_id == donor.id)
        assert match.distance_km is None
        assert "exact distance not available" in match.explanation
    finally:
        db.close()


def test_fresh_availability_ranks_higher():
    db = SessionLocal()
    try:
        fresh = _make_donor(db, "fresh@test.demo", "O+", "ZcityE", "ZareaE",
                            confirmed_hours_ago=1)
        stale = _make_donor(db, "stale@test.demo", "O+", "ZcityE", "ZareaE",
                            confirmed_hours_ago=24 * 45)
        request = _request(db, group="O+", city="ZcityE", locality="ZareaE")
        matches = build_matches(db, request)
        by_donor = {m.donor_id: m for m in matches}
        assert by_donor[fresh.id].score > by_donor[stale.id].score
    finally:
        db.close()


def test_match_rows_persist_and_are_unique():
    db = SessionLocal()
    try:
        donor = _make_donor(db, "persist@test.demo", "O-", "ZcityF", "ZareaF")
        request = _request(db, city="ZcityF", locality="ZareaF")
        first = build_matches(db, request)
        second = build_matches(db, request)
        assert donor.id in {m.donor_id for m in first}
        assert donor.id in {m.donor_id for m in second}
        # Unique (request, donor) constraint: exactly one row after rebuilds
        rows = [m for m in db.query(Match).filter(Match.request_id == request.id,
                                                  Match.donor_id == donor.id).all()]
        assert len(rows) == 1
    finally:
        db.close()
