"""Donor registration and profile management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..deps import require_user
from ..models.donor import Donor
from ..models.user import User
from ..schemas import AvailabilityIn, DonorIn, DonorOut
from ..serializers import donor_public
from ..services.audit import notify

router = APIRouter(prefix="/api/donors", tags=["donors"])


def _get_my_donor(db: Session, user: User) -> Donor | None:
    return db.scalars(select(Donor).where(Donor.user_id == user.id)).first()


@router.post("", response_model=DonorOut)
def create_or_update_donor(data: DonorIn, user: User = Depends(require_user),
                           db: Session = Depends(get_db)):
    """Create or update the signed-in user's donor profile."""
    if user.role == "admin":
        raise HTTPException(403, "Admins do not maintain donor profiles")
    donor = _get_my_donor(db, user)
    if donor is None:
        donor = Donor(user_id=user.id, **data.model_dump())
        db.add(donor)
        notify(db, user.id, "donor_registered", "Donor profile created",
               "Thank you for joining the donor community. Keep your availability "
               "up to date so matching stays accurate.", link="/dashboard/donor")
    else:
        for key, value in data.model_dump().items():
            setattr(donor, key, value)
        donor.last_confirmed_at = utcnow()
    db.commit()
    db.refresh(donor)
    return donor


@router.get("/me", response_model=DonorOut)
def my_donor(user: User = Depends(require_user), db: Session = Depends(get_db)):
    donor = _get_my_donor(db, user)
    if donor is None:
        raise HTTPException(404, "No donor profile yet")
    return donor


@router.patch("/me", response_model=DonorOut)
def update_my_donor(data: DonorIn, user: User = Depends(require_user),
                    db: Session = Depends(get_db)):
    donor = _get_my_donor(db, user)
    if donor is None:
        raise HTTPException(404, "No donor profile yet - use POST /api/donors")
    for key, value in data.model_dump().items():
        setattr(donor, key, value)
    donor.last_confirmed_at = utcnow()
    db.commit()
    db.refresh(donor)
    return donor


@router.patch("/{donor_id}/availability", response_model=DonorOut)
def update_availability(donor_id: int, data: AvailabilityIn,
                        user: User = Depends(require_user), db: Session = Depends(get_db)):
    donor = db.get(Donor, donor_id)
    if donor is None:
        raise HTTPException(404, "Donor not found")
    if user.role != "admin" and donor.user_id != user.id:
        raise HTTPException(403, "You can only update your own availability")
    donor.availability = data.availability
    donor.last_confirmed_at = utcnow()
    db.commit()
    db.refresh(donor)
    return donor


@router.get("")
def list_donors(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Admin-only directory with masked contacts (privacy by design)."""
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    donors = db.scalars(select(Donor).order_by(Donor.created_at.desc())).all()
    out = []
    for d in donors:
        item = donor_public(d)
        u = d.user
        masked = (u.email or "")[:2] + "•••" + (u.email or "")[u.email.find("@"):] if u.email else ""
        item["masked_contact"] = masked
        item["donor_internal_id"] = d.id
        out.append(item)
    return {"donors": out, "count": len(out)}
