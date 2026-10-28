"""Bridge Assistant - conversational blood-request intake.

Two modes:
- Deterministic demo mode (default): a slot-filling state machine. Always works,
  no external service required.
- Optional AI enhancement: when GEMINI_API_KEY is configured, the assistant uses
  the model to extract request details from free-form messages. Every extracted
  value is re-validated server-side; on any API failure/timeout the assistant
  silently falls back to deterministic parsing.

The assistant never invents donors, medical advice, or availability, and never
submits a request without explicit confirmation.
"""
from __future__ import annotations

import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..database import utcnow
from ..models.user import User
from . import compatibility
from .geo import PLACES, lookup_coords

BLOOD_GROUP_OPTIONS = list(compatibility.RECIPIENT_TO_DONORS.keys())
URGENCY_LABELS = {
    "critical": "Critical (needed immediately)",
    "urgent": "Urgent (within 24-48 hours)",
    "routine": "Routine (planned transfusion)",
}

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

SLOT_ORDER = [
    "blood_group", "city", "locality", "hospital", "units", "urgency",
    "needed_by", "requester_name", "contact_value", "notes",
]
OPTIONAL_SLOTS = {"locality", "notes"}

QUESTIONS: dict[str, str] = {
    "blood_group": "Which blood group is needed? For example: O-, B+, AB+.",
    "city": "Which city should I search in?",
    "locality": "Any specific locality or area? (optional - you can say 'skip')",
    "hospital": "Which hospital or collection location is this for?",
    "units": "How many units are needed?",
    "urgency": "How urgent is the request?",
    "needed_by": "By when is the blood needed? (e.g., 'tomorrow 9am', '2026-11-02 18:00')",
    "requester_name": "May I have your name, so donors know who to coordinate with?",
    "contact_value": "What is the best phone number or email for coordination? (with your consent, shared only after a donor accepts contact)",
    "notes": "Any additional details for donors? (optional - you can say 'skip')",
}

CHIPS: dict[str, list[str]] = {
    "blood_group": BLOOD_GROUP_OPTIONS,
    "urgency": list(URGENCY_LABELS.keys()),
    "needed_by": ["today", "tomorrow 9am", "in 12 hours", "in 2 days"],
    "locality": ["skip"],
    "notes": ["skip"],
}


@dataclass
class AssistantState:
    slots: dict[str, Any] = field(default_factory=dict)
    awaiting: str = "slot"  # slot | confirm | done
    current_slot: str = "blood_group"
    submitted_public_id: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)


_SESSIONS: "OrderedDict[str, AssistantState]" = OrderedDict()
_LOCK = threading.Lock()
MAX_SESSIONS = 300


def get_state(session_id: str) -> AssistantState:
    with _LOCK:
        if session_id not in _SESSIONS:
            _SESSIONS[session_id] = AssistantState()
        _SESSIONS.move_to_end(session_id)
        while len(_SESSIONS) > MAX_SESSIONS:
            _SESSIONS.popitem(last=False)
        return _SESSIONS[session_id]


def reset_state(session_id: str) -> AssistantState:
    with _LOCK:
        _SESSIONS[session_id] = AssistantState()
        return _SESSIONS[session_id]


# ---------------------------------------------------------------- parsers

_BG_RE = re.compile(
    r"\b(AB|A|B|O)\s*(POSITIVE|NEGATIVE|POS|NEG|PLUS|MINUS|\+|-|VE)?(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_UNITS_RE = re.compile(r"(\d+)\s*(unit|units|bag|bags|pint|pints|packet|packets)?")
_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_TIME_RE = re.compile(r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE)
_ISO_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?")
_DMY_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?")
_NAME_MONTH_RE = re.compile(r"(\d{1,2})\s+([a-z]{3})|([a-z]{3})\s+(\d{1,2})", re.IGNORECASE)
_IN_RE = re.compile(r"in\s+(\d+)\s+(hour|hours|hr|hrs|day|days)", re.IGNORECASE)
_URGENT_HINT = re.compile(r"\burgent\w*|asap|as soon as possible|24\s*hours|48\s*hours|tonight|today", re.IGNORECASE)
_CRITICAL_HINT = re.compile(r"critical|immediate|right now|emergency|emergenc|icu|accident|life\s*(and\s*death)?|surgery\s*now", re.IGNORECASE)
_ROUTINE_HINT = re.compile(r"routine|planned|elective|not urgent|no rush|scheduled|whenever|next week|next month", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\s-]{7,14}\d)")


def parse_blood_group(text: str) -> str | None:
    for match in _BG_RE.finditer(text):
        candidate = compatibility.validate_group(match.group(0))
        if candidate:
            return candidate
    return None


_CITY_KEYS = {
    "hyderabad", "secunderabad", "bengaluru", "bangalore", "pune", "mumbai",
    "delhi", "new delhi", "chennai", "kolkata", "vijayawada", "warangal",
    "jaipur", "lucknow",
}


def parse_city(text: str) -> tuple[str, str] | None:
    """Returns (city, locality). Uses the local place index first, else free text."""
    lowered = text.lower().strip()
    matches = sorted([p for p in PLACES if p in lowered], key=len, reverse=True)
    city = ""
    locality = ""
    if matches:
        locality = matches[0].title()
        if len(matches) > 1:
            city = matches[1].title()
        if matches[0] in _CITY_KEYS:
            city = city or matches[0].title()
            if len(matches) == 1:
                locality = ""
    if not city:
        near = re.search(r"(?:near|in|around)\s+([a-z][a-z\s-]{2,40})", lowered)
        if near:
            city = near.group(1).strip().title()
    if not city and "," in text:
        first = text.split(",")[0].strip()
        if 2 <= len(first) <= 60 and re.match(r"^[A-Za-z]", first):
            city = first.title()
    if not city and len(text.strip()) <= 60 and re.match(r"^[A-Za-z][A-Za-z\s,.-]+$", text.strip()):
        city = text.strip().title()
    # Free-text locality from the part after a comma when it is not a known place.
    if city and not locality and "," in text:
        rest = text.split(",", 1)[1].strip()
        rest = re.sub(r"^(near|around|in)\s+", "", rest, flags=re.IGNORECASE)
        if 2 <= len(rest) <= 80 and rest.lower() != city.lower():
            locality = rest.title()
    if locality.lower() == city.lower():
        locality = ""
    if city:
        return city, locality
    return None


def parse_units(text: str) -> int | None:
    lowered = text.lower()
    for word, num in _WORD_NUMBERS.items():
        if re.search(rf"\b{word}\b", lowered):
            return num
    m = _UNITS_RE.search(text)
    if m:
        value = int(m.group(1))
        if 1 <= value <= 20:
            return value
    return None


def parse_urgency(text: str) -> str | None:
    lowered = text.lower()
    if _CRITICAL_HINT.search(lowered):
        return "critical"
    if _ROUTINE_HINT.search(lowered):
        return "routine"
    if lowered.strip() in URGENCY_LABELS:
        return lowered.strip()
    if _URGENT_HINT.search(lowered):
        return "urgent"
    return None


def _apply_time(base: Any, text: str) -> Any:
    m = _TIME_RE.search(text)
    if m:
        hour = int(m.group(1)) % 12
        if m.group(3).lower() == "pm":
            hour += 12
        return base.replace(hour=hour, minute=int(m.group(2) or 0), second=0)
    m24 = re.search(r"(\d{1,2}):(\d{2})", text)
    if m24:
        return base.replace(hour=int(m24.group(1)) % 24, minute=int(m24.group(2)), second=0)
    return base.replace(minute=0, second=0)


def parse_needed_by(text: str) -> Any | None:
    text = text.strip()
    lowered = text.lower()
    now = utcnow()

    m = _ISO_RE.search(text)
    if m:
        try:
            dt = now.replace(int(m.group(1)), int(m.group(2)), int(m.group(3)), 0, 0, 0)
        except ValueError:
            return None
        if m.group(4):
            dt = dt.replace(hour=int(m.group(4)), minute=int(m.group(5)))
        return dt

    m = _IN_RE.search(lowered)
    if m:
        amount = int(m.group(1))
        if m.group(2).lower().startswith("h"):
            return now + timedelta(hours=amount)
        return now + timedelta(days=amount)

    m = _DMY_RE.search(text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        try:
            dt = now.replace(year=year, month=month, day=day, hour=9, minute=0, second=0)
        except ValueError:
            return None
        if dt < now and not m.group(3):
            dt = dt.replace(year=year + 1)
        return _apply_time(dt, text)

    m = _NAME_MONTH_RE.search(lowered)
    if m:
        day = int(m.group(1) or m.group(4))
        mon = MONTHS.get((m.group(2) or m.group(3))[:3])
        if mon:
            try:
                dt = now.replace(month=mon, day=day, hour=9, minute=0, second=0)
            except ValueError:
                return None
            if dt < now:
                dt = dt.replace(year=dt.year + 1)
            return _apply_time(dt, text)

    if "tonight" in lowered:
        return _apply_time(now.replace(hour=21, minute=0, second=0), text)
    if "tomorrow" in lowered:
        return _apply_time((now + timedelta(days=1)).replace(hour=9, minute=0, second=0), text)
    if "today" in lowered:
        return _apply_time(now.replace(hour=18, minute=0, second=0), text)
    if lowered in ("asap", "right now", "now", "immediately"):
        return now + timedelta(hours=6)
    return None


def parse_contact(text: str) -> tuple[str, str] | None:
    """Returns (contact_value, contact_method)."""
    email = _EMAIL_RE.search(text)
    if email:
        return email.group(0), "email"
    phone = _PHONE_RE.search(text)
    if phone:
        digits = re.sub(r"[^\d+]", "", phone.group(0))
        if 10 <= len(digits.lstrip("+")) <= 15:
            return digits, "phone"
    return None


def _auto_fill_slots(state: AssistantState, text: str) -> list[str]:
    """Best-effort extraction of later slots from the same message.

    Users often give several details at once ("O negative in Pune urgently").
    Only high-confidence parses are accepted - known cities, explicit unit
    words, urgency keywords, and parseable future dates - so the assistant
    never invents values. Free-text slots (hospital, name, contact) are
    never auto-filled.
    """
    filled: list[str] = []
    for slot in SLOT_ORDER:
        if slot == "blood_group" or slot in state.slots or slot in OPTIONAL_SLOTS:
            continue
        if slot == "city":
            parsed = parse_city(text)
            if parsed and parsed[0] and parsed[0].lower() in _CITY_KEYS:
                state.slots["city"] = parsed
                filled.append(slot)
        elif slot == "units":
            # Require an explicit unit word so "9am" or "ward 3" never counts.
            if re.search(r"\b(units?|bags?|pints?|packets?)\b", text, re.IGNORECASE):
                value = parse_units(text)
                if value is not None:
                    state.slots["units"] = value
                    filled.append(slot)
        elif slot == "urgency":
            value = parse_urgency(text)
            if value is not None:
                state.slots["urgency"] = value
                filled.append(slot)
        elif slot == "needed_by":
            value = parse_needed_by(text)
            if value is not None and value > utcnow():
                state.slots["needed_by"] = value
                filled.append(slot)
    return filled


def parse_slot(slot: str, text: str) -> tuple[Any, str | None]:
    """Parse a value for `slot`. Returns (value, error_message)."""
    cleaned = text.strip()
    if slot == "blood_group":
        value = parse_blood_group(cleaned)
        if not value:
            return None, "I didn't catch a valid blood group. Please use one of: " + ", ".join(BLOOD_GROUP_OPTIONS) + "."
        return value, None
    if slot == "city":
        parsed = parse_city(cleaned)
        if not parsed or not parsed[0]:
            return None, "Which city should I search in? Please name a city (e.g., Hyderabad)."
        return parsed, None
    if slot == "locality":
        if cleaned.lower() in ("skip", "none", "no", "n/a", "na", "-"):
            return "", None
        return cleaned[:160].title(), None
    if slot == "hospital":
        cleaned = re.sub(r"^(at|in|it'?s|hospital is|the hospital is)\s+", "", cleaned, flags=re.IGNORECASE)
        if len(cleaned) < 2:
            return None, "Please share the hospital or collection location name."
        return cleaned[:200], None
    if slot == "units":
        value = parse_units(cleaned)
        if value is None:
            return None, "How many units are needed? Please give a number between 1 and 20."
        return value, None
    if slot == "urgency":
        value = parse_urgency(cleaned)
        if not value:
            return None, "Please describe urgency as one of: critical, urgent, or routine."
        return value, None
    if slot == "needed_by":
        value = parse_needed_by(cleaned)
        if value is None:
            return None, "I couldn't read that date. Try something like 'tomorrow 9am', 'in 12 hours', or '2026-11-02 18:00'."
        if value <= utcnow():
            return None, "The needed-by time must be in the future. When do you need the blood?"
        if value > utcnow() + timedelta(days=90):
            return None, "Requests can be scheduled up to 90 days ahead. Please pick an earlier date."
        return value, None
    if slot == "requester_name":
        cleaned = re.sub(r"^(i am|i'm|my name is|this is|name:?)\s+", "", cleaned, flags=re.IGNORECASE)
        if not re.match(r"^[A-Za-z][A-Za-z\s.'-]{1,60}$", cleaned):
            return None, "Please share your name (letters only)."
        return cleaned.strip().title(), None
    if slot == "contact_value":
        parsed = parse_contact(cleaned)
        if not parsed:
            return None, "Please share a valid phone number (10-15 digits) or an email address."
        return parsed, None
    if slot == "notes":
        if cleaned.lower() in ("skip", "none", "no", "n/a", "na", "-"):
            return "", None
        return cleaned[:1000], None
    return None, f"Unknown slot {slot}"


# ---------------------------------------------------------------- FAQ

FAQ: list[tuple[str, str]] = [
    ("how does matching work",
     "Matching filters registered donors by blood compatibility, active availability, "
     "discoverability consent and geographic relevance, then ranks them by proximity, "
     "availability freshness and preferences. It's preliminary donor discovery - not a "
     "guarantee, and not medical clearance."),
    ("will you find blood",
     "I can't promise that. BloodBridge helps you discover potential donors, but "
     "availability is never guaranteed. For urgent needs, please also contact your "
     "nearest blood bank or hospital blood centre right away."),
    ("blood bank",
     "For time-critical needs, contact the hospital blood bank or a regional blood "
     "centre first - they maintain real-time inventory. BloodBridge complements that "
     "by helping you discover potential community donors."),
    ("eligib",
     "Final donation eligibility is always decided by qualified blood-donation "
     "professionals at the donation site. BloodBridge profiles only express "
     "willingness and availability - never medical clearance."),
    ("privacy",
     "Your phone number, exact address and precise coordinates are never shown "
     "publicly. Requesters only see your blood group, general locality, approximate "
     "distance and availability status. Contact details are shared only after you "
     "accept a contact request."),
    ("reward",
     "Community rewards recognise participation - like completing onboarding, "
     "education modules or community events - with badges, certificates and approved "
     "non-cash partner offers. Rewards are never given for donating blood, and never "
     "cash."),
    ("referral",
     "Every member gets a unique invite link. When someone you invited joins and "
     "completes community onboarding, you can earn non-cash recognition like badges "
     "or certificates - subject to campaign rules and review. Referrals are never "
     "paid for blood donations."),
    ("whatsapp",
     "You can use this WhatsApp-style chat right here in the app. If our official "
     "WhatsApp Business number is configured, the same assistant works over WhatsApp "
     "with your consent. Demo chats are clearly labelled as simulations."),
]


def faq_answer(text: str) -> str | None:
    lowered = text.lower().strip()
    if len(lowered) < 8 or not lowered.endswith("?") and not re.match(r"^(what|how|why|who|can|is|are|do|does|will|should|when|where)\b", lowered):
        return None
    for key, answer in FAQ:
        if key in lowered:
            return answer
    if lowered.endswith("?"):
        return ("I can help with creating blood requests, matching, rewards and referrals. "
                "For medical questions, please consult a qualified healthcare professional.")
    return None


# ---------------------------------------------------------------- optional LLM

_LLM_SYSTEM = (
    "You extract blood request details from a conversation. Reply with ONLY a JSON "
    "object using these keys when the user provides them: blood_group (one of O-, O+, "
    "A-, A+, B-, B+, AB-, AB+), city, locality, hospital, units (int), urgency "
    "(critical|urgent|routine), needed_by (ISO YYYY-MM-DD HH:MM), requester_name, "
    "contact_value, notes. Omit unknown keys. No prose."
)


def llm_extract(message: str, state: AssistantState) -> dict[str, Any] | None:
    if not settings.gemini_api_key:
        return None
    convo = "\n".join(f"{h['role']}: {h['text']}" for h in state.history[-8:])
    prompt = f"{_LLM_SYSTEM}\n\nConversation so far:\n{convo}\nUser: {message}\nJSON:"
    try:
        resp = httpx.post(
            f"{settings.gemini_base_url}/v1beta/models/{settings.gemini_model}:generateContent",
            params={"key": settings.gemini_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}},
            timeout=6.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text_out = data["candidates"][0]["content"]["parts"][0]["text"]
        text_out = re.sub(r"^```(?:json)?|```$", "", text_out.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(text_out)
        return parsed if isinstance(parsed, dict) else None
    except Exception:  # noqa: BLE001 - any failure falls back to deterministic mode
        return None


def _merge_llm(db: Session | None, state: AssistantState, extracted: dict[str, Any]) -> list[str]:
    """Validate + merge LLM-extracted fields. Returns names of slots filled."""
    filled: list[str] = []
    for slot in SLOT_ORDER:
        if slot in state.slots or slot not in extracted:
            continue
        raw = extracted[slot]
        if slot == "needed_by" and isinstance(raw, str):
            value = parse_needed_by(raw)
            if value and value > utcnow():
                state.slots[slot] = value
                filled.append(slot)
            continue
        if slot == "city":
            parsed = parse_city(str(raw))
            if parsed and parsed[0]:
                state.slots[slot] = parsed
                filled.append(slot)
            continue
        if slot == "contact_value":
            parsed = parse_contact(str(raw))
            if parsed:
                state.slots[slot] = parsed
                filled.append(slot)
            continue
        value, err = parse_slot(slot, str(raw))
        if value is not None and not err:
            state.slots[slot] = value
            filled.append(slot)
    return filled


# ---------------------------------------------------------------- core flow

def _next_missing_slot(state: AssistantState, user: User | None) -> str | None:
    for slot in SLOT_ORDER:
        if slot in state.slots:
            continue
        if user and slot == "requester_name":
            state.slots["requester_name"] = user.name
            continue
        if user and slot == "contact_value" and (user.phone or user.email):
            value = user.phone or user.email
            method = "phone" if user.phone else "email"
            state.slots["contact_value"] = (value, method)
            continue
        if slot in OPTIONAL_SLOTS:
            continue  # offered at the end instead
        return slot
    return None


def _proposal(state: AssistantState) -> dict[str, Any] | None:
    if not all(s in state.slots for s in SLOT_ORDER if s not in OPTIONAL_SLOTS):
        return None
    s = state.slots
    city, locality = s["city"] if isinstance(s["city"], tuple) else (s["city"], "")
    contact_value, contact_method = s["contact_value"] if isinstance(s["contact_value"], tuple) else (s["contact_value"], "phone")
    return {
        "blood_group": s["blood_group"],
        "city": city,
        "locality": locality,
        "hospital": s["hospital"],
        "units": s["units"],
        "urgency": s["urgency"],
        "needed_by": s["needed_by"].strftime("%Y-%m-%d %H:%M"),
        "requester_name": s["requester_name"],
        "contact_value": contact_value,
        "contact_method": contact_method,
        "notes": s.get("notes", ""),
    }


def _summary_text(proposal: dict[str, Any]) -> str:
    return (
        "Here's your request summary:\n"
        f"• Blood group: {proposal['blood_group']}\n"
        f"• Location: {proposal['locality'] + ', ' if proposal['locality'] else ''}{proposal['city']}\n"
        f"• Hospital: {proposal['hospital']}\n"
        f"• Units: {proposal['units']}\n"
        f"• Urgency: {URGENCY_LABELS[proposal['urgency']]}\n"
        f"• Needed by: {proposal['needed_by']}\n"
        f"• Coordinator: {proposal['requester_name']} ({proposal['contact_method']})\n"
        "Shall I submit this request? You can also say 'edit <field>' to change something."
    )


def handle_message(
    db: Session,
    session_id: str,
    message: str,
    user: User | None,
) -> dict[str, Any]:
    state = get_state(session_id)
    text = (message or "").strip()
    state.history.append({"role": "user", "text": text[:500]})
    if len(state.history) > 40:
        del state.history[:-40]

    lowered = text.lower()

    # --- restart / done handling
    if lowered in ("start over", "restart", "reset"):
        state = reset_state(session_id)
        reply = ("No problem - let's start fresh. " + QUESTIONS["blood_group"])
        return _respond(state, reply, chips=CHIPS["blood_group"])

    if state.awaiting == "done":
        if lowered in ("new request", "another request", "start over"):
            state = reset_state(session_id)
            return _respond(state, "Let's create a new request. " + QUESTIONS["blood_group"],
                            chips=CHIPS["blood_group"])
        return _respond(state, state.history and "Your request has been submitted. Is there anything else? "
                        "You can say 'new request' to start another one." or "",
                        chips=["new request"])

    # --- greeting / bootstrap (fresh sessions only; clients send "start" on load)
    if not state.slots and lowered in ("", "start", "hi", "hello", "hey", "help",
                                       "hi!", "hello!", "hey!"):
        reply = ("Hello! I'm Bridge Assistant, and I can help you create a blood request "
                 "step by step. " + QUESTIONS["blood_group"])
        return _respond(state, reply, chips=CHIPS["blood_group"])

    # --- approval gate (explicit confirmation required)
    if state.awaiting == "confirm":
        if lowered in ("__approve__", "confirm", "yes", "approve", "submit", "correct", "that's right", "looks good"):
            return _submit(db, state, user)
        edit = re.match(r"edit\s+(.+)", lowered)
        if edit:
            field_text = edit.group(1).strip()
            alias = {"blood group": "blood_group", "group": "blood_group", "city": "city",
                     "location": "city", "area": "locality", "locality": "locality",
                     "hospital": "hospital", "units": "units", "urgency": "urgency",
                     "time": "needed_by", "needed by": "needed_by", "date": "needed_by",
                     "name": "requester_name", "contact": "contact_value",
                     "phone": "contact_value", "email": "contact_value", "notes": "notes"}
            slot = None
            for key, target in alias.items():
                if key in field_text:
                    slot = target
                    break
            if slot:
                state.slots.pop(slot, None)
                if slot == "city":
                    state.slots.pop("locality", None)
                state.awaiting = "slot"
                state.current_slot = slot
                return _respond(state, f"Sure - let's update that. {QUESTIONS[slot]}",
                                chips=CHIPS.get(slot, []))
            return _respond(state, "Which field would you like to edit? For example: 'edit blood group', "
                            "'edit units', 'edit time'.")
        # try to capture a correction for a known slot
        for slot in ("blood_group", "units", "urgency"):
            value, err = parse_slot(slot, text)
            if value is not None and not err:
                state.slots[slot] = value
                proposal = _proposal(state)
                return _respond(state, f"Updated. {_summary_text(proposal)}", proposal=proposal)
        answer = faq_answer(text)
        if answer:
            return _respond(state, answer + "\n\n" + _summary_text(_proposal(state)) if _proposal(state) else answer)
        proposal = _proposal(state)
        return _respond(state, "Please reply 'confirm' to submit, or 'edit <field>' to change something.",
                        proposal=proposal)

    # --- slot filling
    if state.awaiting == "slot":
        # FAQ interruptions don't lose progress
        answer = faq_answer(text)
        slot = state.current_slot

        value, err = parse_slot(slot, text)
        if value is None:
            # LLM fallback for free-form input (only when configured)
            extracted = llm_extract(text, state)
            if extracted:
                filled = _merge_llm(db, state, extracted)
                if slot in filled:
                    value, err = state.slots.get(slot), None
        if value is not None and err is None:
            if slot == "city":
                state.slots["city"] = value  # (city, locality) tuple
            elif slot == "contact_value":
                state.slots["contact_value"] = value  # (value, method) tuple
            else:
                state.slots[slot] = value
            auto_filled = _auto_fill_slots(state, text)
            next_slot = _next_missing_slot(state, user)
            if next_slot is None:
                # offer optional slots, then confirm
                if "locality" not in state.slots:
                    state.current_slot = "locality"
                    return _respond(state, "Got it. " + QUESTIONS["locality"], chips=CHIPS["locality"])
                if "notes" not in state.slots:
                    state.current_slot = "notes"
                    return _respond(state, "Almost done. " + QUESTIONS["notes"], chips=CHIPS["notes"])
                state.awaiting = "confirm"
                proposal = _proposal(state)
                return _respond(state, _summary_text(proposal), proposal=proposal)
            state.current_slot = next_slot
            if slot == "blood_group" and not auto_filled:
                prefix = "Noted. "
            else:
                noted = [slot] + auto_filled
                names = ", ".join(s.replace("_", " ") for s in noted)
                prefix = f"Great - {names} noted. "
            return _respond(state, prefix + QUESTIONS[next_slot], chips=CHIPS.get(next_slot, []))
        if err:
            if answer:
                return _respond(state, answer + "\n\n" + QUESTIONS[slot], chips=CHIPS.get(slot, []))
            return _respond(state, err, chips=CHIPS.get(slot, []))

    # --- fresh session
    if not state.slots and state.current_slot == "blood_group":
        reply = ("Hello! I'm Bridge Assistant, and I can help you create a blood request "
                 "step by step. " + QUESTIONS["blood_group"])
        return _respond(state, reply, chips=CHIPS["blood_group"])

    answer = faq_answer(text)
    if answer:
        return _respond(state, answer)
    state.current_slot = _next_missing_slot(state, user) or state.current_slot
    return _respond(state, QUESTIONS.get(state.current_slot, "How can I help?"),
                    chips=CHIPS.get(state.current_slot, []))


def _submit(db: Session, state: AssistantState, user: User | None) -> dict[str, Any]:
    from .request_service import create_request_from_assistant
    proposal = _proposal(state)
    try:
        request = create_request_from_assistant(db, proposal, user)
    except ValueError as exc:
        return _respond(state, f"I couldn't submit that: {exc}. Let's fix it - "
                        f"{QUESTIONS.get(state.current_slot, 'please review the details')}.")
    state.awaiting = "done"
    state.submitted_public_id = request.public_id
    reply = (
        f"Done! Your request {request.public_id} is submitted and I'm looking for "
        "potentially compatible donors near "
        f"{request.locality + ', ' if request.locality else ''}{request.city}.\n\n"
        "What happens next:\n"
        "1. Compatible, available donors are ranked by proximity and availability.\n"
        "2. You can initiate permitted contact from the request page.\n"
        "3. Donors decide whether to respond - nothing is automatic.\n\n"
        f"Track it here: /requests/{request.public_id}\n\n"
        "Please note: BloodBridge supports discovery only - it does not guarantee that "
        "blood or donors will be found, and matching is not medical clearance. For "
        "emergencies, contact your hospital or blood bank immediately."
    )
    return _respond(state, reply, done=True, request_public_id=request.public_id)


def _respond(state: AssistantState, reply: str, chips: list[str] | None = None,
             proposal: dict | None = None, done: bool = False,
             request_public_id: str | None = None) -> dict[str, Any]:
    state.history.append({"role": "assistant", "text": reply[:500]})
    return {
        "reply": reply,
        "chips": chips or [],
        "proposal": proposal,
        "awaiting": state.awaiting,
        "done": done or state.awaiting == "done",
        "request_public_id": request_public_id or state.submitted_public_id,
        "mode": "ai_enhanced" if settings.gemini_api_key else "deterministic_demo",
        "disclaimer": ("BloodBridge does not provide medical advice, does not guarantee "
                       "donors or blood availability, and never submits a request without "
                       "your explicit confirmation."),
    }
