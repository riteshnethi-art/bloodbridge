"""Blood compatibility engine (red blood cell donor discovery).

IMPORTANT: These rules support preliminary donor *discovery* only. Actual
transfusion compatibility (including Rh subtypes, red cell antigen testing and
crossmatching) must be assessed by qualified healthcare professionals.
"""
from __future__ import annotations

from ..models.donor import VALID_BLOOD_GROUPS

# Recipient -> compatible red blood cell donor groups.
# O-negative can only receive O-negative. AB-positive can receive anything.
RECIPIENT_TO_DONORS: dict[str, tuple[str, ...]] = {
    "O-":  ("O-",),
    "O+":  ("O-", "O+"),
    "A-":  ("O-", "A-"),
    "A+":  ("O-", "O+", "A-", "A+"),
    "B-":  ("O-", "B-"),
    "B+":  ("O-", "O+", "B-", "B+"),
    "AB-": ("O-", "A-", "B-", "AB-"),
    "AB+": ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"),
}

DISCOVERY_NOTICE = (
    "These results support preliminary donor discovery only. Blood transfusion "
    "compatibility and donor eligibility must be assessed by qualified healthcare "
    "professionals, including appropriate testing and crossmatching."
)


def validate_group(group: str) -> str | None:
    """Normalize a blood group string; returns canonical form or None.

    Accepts forms like "B positive", "B+", "bpos", "AB NEGATIVE", "AB-".
    """
    g = (group or "").strip().upper().replace(" ", "")
    for word, sign in (
        ("POSITIVE", "+"), ("NEGATIVE", "-"),
        ("POS", "+"), ("NEG", "-"),
        ("PLUS", "+"), ("MINUS", "-"),
    ):
        g = g.replace(word, sign)
    return g if g in VALID_BLOOD_GROUPS else None


def compatible_donor_groups(recipient_group: str) -> tuple[str, ...]:
    """Return the tuple of donor groups compatible with `recipient_group`.

    Raises ValueError for unknown recipient groups so callers can't silently
    proceed with wrong data.
    """
    g = validate_group(recipient_group)
    if g is None:
        raise ValueError(f"Unknown blood group: {recipient_group!r}. Expected one of {VALID_BLOOD_GROUPS}.")
    return RECIPIENT_TO_DONORS[g]


def is_compatible(recipient_group: str, donor_group: str) -> bool:
    dg = validate_group(donor_group)
    if dg is None:
        return False
    return dg in compatible_donor_groups(recipient_group)
