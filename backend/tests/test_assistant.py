"""Bridge Assistant tests: slot filling, validation, confirmation gate."""
from __future__ import annotations

from app.database import SessionLocal
from app.models.request import BloodRequest
from app.services import assistant


def _drive(session_id: str, turns: list[str]) -> list[dict]:
    db = SessionLocal()
    try:
        outs = []
        for turn in turns:
            outs.append(assistant.handle_message(db, session_id, turn, user=None))
        return outs
    finally:
        db.close()


def test_full_happy_path_via_confirm_button():
    outs = _drive("s-happy", [
        "B positive",
        "Hyderabad, near Gachibowli",
        "Demo Multispeciality Hospital",
        "2 units",
        "urgent",
        "tomorrow 9am",
        "Rahul Mehta",
        "+919812345678",
        "skip",  # locality
        "skip",  # notes
    ])
    # After all slots are filled the assistant asks for confirmation.
    final = outs[-1]
    assert final["awaiting"] == "confirm"
    assert final["proposal"]["blood_group"] == "B+"
    assert final["proposal"]["city"] == "Hyderabad"
    assert final["proposal"]["units"] == 2
    # Explicit confirmation required - nothing submitted yet.
    assert final["request_public_id"] is None
    submit = assistant.handle_message(SessionLocal(), "s-happy", "__approve__", user=None)
    assert submit["done"] is True
    assert submit["request_public_id"] and submit["request_public_id"].startswith("BB-")
    db = SessionLocal()
    try:
        request = db.query(BloodRequest).filter(
            BloodRequest.public_id == submit["request_public_id"]).first()
        assert request is not None
        assert request.blood_group == "B+"
        assert request.locality == "Gachibowli"
        assert request.contact_method == "phone"
    finally:
        db.close()


def test_invalid_blood_group_is_rejected():
    outs = _drive("s-badgroup", ["Z positive"])
    assert "didn't catch a valid blood group" in outs[0]["reply"]


def test_needed_by_must_be_future():
    outs = _drive("s-past", ["O-", "Hyderabad", "Demo Hospital", "1 unit",
                             "routine", "2020-01-01 10:00"])
    assert "future" in outs[-1]["reply"]


def test_faq_does_not_lose_progress():
    outs = _drive("s-faq", ["B positive", "How does matching work?"])
    assert "preliminary donor discovery" in outs[1]["reply"]
    # Progress retained: next expected question is city.
    nxt = assistant.handle_message(SessionLocal(), "s-faq", "Hyderabad", user=None)
    assert "hospital" in nxt["reply"].lower()


def test_edit_before_confirmation():
    _drive("s-edit", ["A positive", "Hyderabad", "Demo Hospital", "1 unit",
                      "routine", "tomorrow", "Test User", "test@example.demo",
                      "skip", "skip"])
    edited = assistant.handle_message(SessionLocal(), "s-edit", "edit blood group", user=None)
    assert "update" in edited["reply"].lower()
    fixed = assistant.handle_message(SessionLocal(), "s-edit", "O negative", user=None)
    assert fixed["proposal"]["blood_group"] == "O-"
    assert fixed["awaiting"] == "confirm"


def test_never_submits_without_confirmation():
    outs = _drive("s-noconfirm", ["O-", "Hyderabad", "Demo Hospital", "1 unit",
                                  "urgent", "tomorrow", "Test User",
                                  "+919812345678", "skip", "skip"])
    assert outs[-1]["request_public_id"] is None
    assert outs[-1]["awaiting"] == "confirm"


def test_deterministic_mode_is_default():
    db = SessionLocal()
    try:
        result = assistant.handle_message(db, "s-mode", "hello", user=None)
        assert result["mode"] == "deterministic_demo"
    finally:
        db.close()


def test_start_message_gets_greeting():
    """Bootstrap messages ("start"/"hi") greet instead of failing blood-group parse."""
    outs = _drive("s-boot", ["start"])
    assert "blood group" in outs[0]["reply"].lower()
    assert outs[0]["request_public_id"] is None
    # Repeated bootstrap messages stay friendly and never corrupt state.
    again = assistant.handle_message(SessionLocal(), "s-boot", "hi", user=None)
    assert "blood group" in again["reply"].lower()
    state = assistant.get_state("s-boot")
    assert state.slots == {}


def test_multi_slot_extraction_from_first_message():
    """One rich message fills blood group, city and urgency together."""
    outs = _drive("s-multi", ["I need O negative blood in Pune urgently"])
    first = outs[0]
    # The assistant skips straight to the hospital question.
    assert "hospital" in first["reply"].lower()
    state = assistant.get_state("s-multi")
    assert state.slots["blood_group"] == "O-"
    assert state.slots["city"][0] == "Pune"
    assert state.slots["urgency"] == "urgent"
    # Finish the flow: captured values must reach the proposal and the request.
    rest = _drive("s-multi", ["Demo Hospital", "2 units", "tomorrow 9am",
                              "Test User", "+919812345678", "skip", "skip"])
    final = rest[-1]
    assert final["awaiting"] == "confirm"
    assert final["request_public_id"] is None
    assert final["proposal"]["blood_group"] == "O-"
    assert final["proposal"]["city"] == "Pune"
    assert final["proposal"]["urgency"] == "urgent"
    submit = assistant.handle_message(SessionLocal(), "s-multi", "__approve__", user=None)
    assert submit["done"] is True
    db = SessionLocal()
    try:
        request = db.query(BloodRequest).filter(
            BloodRequest.public_id == submit["request_public_id"]).first()
        assert request is not None
        assert request.blood_group == "O-"
        assert request.city == "Pune"
        assert request.urgency == "urgent"
    finally:
        db.close()
