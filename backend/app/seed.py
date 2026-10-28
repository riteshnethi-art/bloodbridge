"""Fictional demo seed data. Clearly labelled for the hackathon demo.

Demo accounts (all passwords: demo123):
- admin@bloodbridge.demo  (admin)
- rahul@example.demo      (requester)
- priya@example.demo      (requester)
- plus 10 donors, e.g. aarav.donor@bloodbridge.demo
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import SessionLocal, create_all, utcnow
from .models.donor import Donor
from .models.referral import ReferralCampaign
from .models.rewards import RewardOffer
from .models.request import BloodRequest
from .models.user import User
from .security import hash_password
from .services.geo import PLACES
from .services.request_service import create_request

PASSWORD = "demo123"


def seed_if_empty() -> None:
    create_all()
    from .config import settings
    if not settings.seed_demo_data:
        return
    db = SessionLocal()
    try:
        if db.scalar(select(func.count(User.id))):
            return
        _seed(db)
        db.commit()
    finally:
        db.close()


def _coords(city: str, locality: str):
    from .services.geo import lookup_coords
    return lookup_coords(city, locality)


def _seed(db: Session) -> None:
    now = utcnow()

    admin = User(name="BloodBridge Admin", email="admin@bloodbridge.demo",
                 password_hash=hash_password(PASSWORD), role="admin", email_verified=True)
    rahul = User(name="Rahul Mehta", email="rahul@example.demo",
                 password_hash=hash_password(PASSWORD), role="requester",
                 email_verified=True, phone="+919810011223")
    priya = User(name="Priya Desai", email="priya@example.demo",
                 password_hash=hash_password(PASSWORD), role="requester",
                 email_verified=True, phone="+919810044556")
    db.add_all([admin, rahul, priya])

    donor_specs = [
        ("Aarav Sharma", "aarav.donor@bloodbridge.demo", "O+", "Hyderabad", "Gachibowli", "available", True),
        ("Diya Patel", "diya.donor@bloodbridge.demo", "O-", "Hyderabad", "Madhapur", "available", True),
        ("Rohan Verma", "rohan.donor@bloodbridge.demo", "A+", "Hyderabad", "Secunderabad", "maybe", True),
        ("Ananya Rao", "ananya.donor@bloodbridge.demo", "B+", "Hyderabad", "Hitech City", "available", False),
        ("Kabir Nair", "kabir.donor@bloodbridge.demo", "AB+", "Bengaluru", "Koramangala", "available", True),
        ("Meera Iyer", "meera.donor@bloodbridge.demo", "O+", "Pune", "Kothrud", "available", True),
        ("Arjun Reddy", "arjun.donor@bloodbridge.demo", "B-", "Hyderabad", "Gachibowli", "maybe", True),
        ("Sneha Kulkarni", "sneha.donor@bloodbridge.demo", "A-", "Pune", "Baner", "available", True),
        ("Vikram Singh", "vikram.donor@bloodbridge.demo", "O-", "Delhi", "Dwarka", "unavailable", True),
        ("Ishita Bose", "ishita.donor@bloodbridge.demo", "AB-", "Kolkata", "Salt Lake", "available", True),
    ]
    donors: list[Donor] = []
    for name, email, group, city, locality, availability, discoverable in donor_specs:
        user = User(name=name, email=email, password_hash=hash_password(PASSWORD),
                    role="donor", email_verified=True, phone=f"+9198{abs(hash(email)) % 100000000:08d}")
        db.add(user)
        db.flush()
        coords = _coords(city, locality)
        jitter = ((abs(hash(email)) % 100) - 50) / 2000  # tiny deterministic offset
        donor = Donor(
            user_id=user.id, blood_group=group, city=city, locality=locality,
            lat=coords[0] + jitter if coords else None,
            lng=coords[1] + jitter if coords else None,
            availability=availability, last_confirmed_at=now - timedelta(hours=abs(hash(email)) % 72),
            discoverable=discoverable, preferred_contact="in_app",
            allow_direct_contact=abs(hash(email)) % 3 == 0,
        )
        db.add(donor)
        donors.append(donor)
    db.flush()

    # Demo offers - all with fictional "Demo Partner" labels.
    offers = [
        ("Demo Partner: Hitech Pharmacy", "Health Check Discount",
         "15% off a basic health check-up package for active community members.",
         "health", 50, "Show your claim code at the counter.",
         "Demo offer for the hackathon build. Not a real business partner. One redemption per member."),
        ("Demo Café: Community Corner", "Community Coffee 10% Off",
         "10% off any beverage - a small thank-you for participating in community onboarding.",
         "food", 100, "Show your claim code at checkout.",
         "Demo offer for the hackathon build. Not a real business partner."),
        ("Demo Bookstore: PageTurners", "Reading Voucher",
         "Redeem a reading voucher towards any health or wellness book.",
         "education", 30, "Share your claim code with the store desk.",
         "Demo offer for the hackathon build. Not a real business partner."),
        ("Demo Sports Store: FitHub", "Hygiene Kit",
         "Redeem a basic personal hygiene kit after completing an education module.",
         "wellness", 40, "Show your claim code and recognition in your wallet.",
         "Demo offer for the hackathon build. Not a real business partner."),
    ]
    for partner, title, desc, category, qty, redeem, terms in offers:
        db.add(RewardOffer(
            offer_ref=f"OFF-{abs(hash(title)) % 999999:06d}",
            partner_name=partner, is_demo_partner=True, title=title, description=desc,
            category=category, quantity=qty, remaining=qty,
            valid_to=now + timedelta(days=180), redemption_instructions=redeem,
            terms=terms, status="active",
        ))

    db.add(ReferralCampaign(
        name="Community Onboarding Campaign",
        description=("Earn a Community Connector Badge when someone you invited joins "
                     "BloodBridge and completes community onboarding. Recognition only - "
                     "never cash, and never tied to blood donation."),
        start_at=now - timedelta(days=1), end_at=now + timedelta(days=120),
        eligible_event="onboarding_completed", reward_type="badge",
        per_user_limit=10, total_limit=500, auto_approve=False, requires_review=True,
        eligibility_rules=("The invited member must: register with a unique verified "
                           "account, complete community onboarding, and pass duplicate/"
                           "abuse checks. The reward is never conditional on donating "
                           "blood or responding to any request."),
        terms=("Non-cash recognition only. BloodBridge may pause or end campaigns at "
               "any time. Suspected abuse is reviewed by administrators; flagged "
               "accounts are not automatically banned."),
        status="active", approval_note="Approved for demo launch by demo admin.",
        created_by=admin.id,
    ))

    # One live demo request (guest-style, owned by priya).
    create_request(db, {
        "blood_group": "O-",
        "city": "Hyderabad",
        "locality": "Madhapur",
        "hospital": "Demo Multispeciality Hospital",
        "units": 2,
        "urgency": "urgent",
        "needed_by": now + timedelta(days=1, hours=4),
        "requester_name": priya.name,
        "contact_value": priya.phone or priya.email,
        "contact_method": "phone",
        "notes": "Demo request seeded for the hackathon walkthrough.",
    }, priya)
