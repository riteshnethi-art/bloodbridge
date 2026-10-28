"""Compatibility engine tests - every recipient group, independent of the API."""
from __future__ import annotations

import pytest

from app.services.compatibility import (
    DISCOVERY_NOTICE, RECIPIENT_TO_DONORS, compatible_donor_groups, is_compatible,
    validate_group,
)


def test_o_negative_can_only_receive_o_negative():
    assert compatible_donor_groups("O-") == ("O-",)


def test_ab_positive_receives_everything():
    assert set(compatible_donor_groups("AB+")) == set(RECIPIENT_TO_DONORS["AB+"])
    assert len(compatible_donor_groups("AB+")) == 8


@pytest.mark.parametrize("recipient,expected", [
    ("O-", {"O-"}),
    ("O+", {"O-", "O+"}),
    ("A-", {"O-", "A-"}),
    ("A+", {"O-", "O+", "A-", "A+"}),
    ("B-", {"O-", "B-"}),
    ("B+", {"O-", "O+", "B-", "B+"}),
    ("AB-", {"O-", "A-", "B-", "AB-"}),
    ("AB+", {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"}),
])
def test_all_recipient_groups(recipient: str, expected: set[str]):
    assert set(compatible_donor_groups(recipient)) == expected


@pytest.mark.parametrize("recipient", list(RECIPIENT_TO_DONORS))
def test_compatible_donors_can_receive_their_own_group(recipient: str):
    assert is_compatible(recipient, recipient)


def test_incompatible_pairs():
    assert not is_compatible("O-", "O+")
    assert not is_compatible("A-", "B-")
    assert not is_compatible("O+", "AB-")
    assert not is_compatible("B+", "A+")


def test_unknown_group_raises():
    with pytest.raises(ValueError):
        compatible_donor_groups("Z+")


def test_normalize_forms():
    assert validate_group("b positive") == "B+"
    assert validate_group("AB NEGATIVE") == "AB-"
    assert validate_group("o-") == "O-"
    assert validate_group("O POS") == "O+"
    assert validate_group("nonsense") is None
    assert validate_group("") is None


def test_discovery_notice_present():
    assert "qualified healthcare professionals" in DISCOVERY_NOTICE
    assert "crossmatching" in DISCOVERY_NOTICE
