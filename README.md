# BloodBridge

AI-assisted blood donor discovery, matching, community rewards & referral platform.

BloodBridge helps people discover **potentially compatible** blood donors based on blood
group, location, donor availability and urgency — with conversational request intake
(Bridge Assistant), a WhatsApp-style chat experience, transparent matching, community
rewards, and a referral program ("BloodBridge Community Invites").

> **Safety notice.** BloodBridge supports preliminary donor discovery only. It does not
> provide medical advice, does not guarantee donors or blood availability, and never
> replaces professional transfusion services. Compatibility and donor eligibility must be
> assessed by qualified healthcare professionals, including appropriate testing and
> crossmatching. In an emergency, contact your hospital or blood bank immediately.

---

## Quick start (hackathon demo)

Prerequisites: **Python 3.12+** and **Node 18+** (tested on Python 3.14 / Node 24).

### 1. Backend (FastAPI)

```powershell
cd bloodbridge\backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000 --reload
```

- API: http://127.0.0.1:8000 — interactive docs at `/docs`
- Health: http://127.0.0.1:8000/health
- On first start the database (`bloodbridge.db`, SQLite) is created and **fictional demo
  data is seeded** automatically.

### 2. Frontend (React + Vite)

```powershell
cd bloodbridge\frontend
npm install
npm run dev
```

- App: http://localhost:5173 (dev server proxies `/api` and `/health` to port 8000)

### 3. Tests

```powershell
# Backend (61 tests: compatibility, matching, assistant, rewards, referrals, API flows)
cd bloodbridge\backend
python -m pytest tests -q

# Frontend (10 tests: form validation + UI kit)
cd bloodbridge\frontend
npm test
```

### Demo accounts (password `demo123`)

| Role | Email |
|---|---|
| Admin | `admin@bloodbridge.demo` |
| Requester | `rahul@example.demo`, `priya@example.demo` |
| Donor | `aarav.donor@bloodbridge.demo`, `diya.donor@bloodbridge.demo`, `arjun.donor@bloodbridge.demo`, … (10 donors) |

All demo partners in the rewards catalogue are labelled **"Demo Partner (not a real
business)"**. All seed data is fictional.

---

## Feature map

| Module | Where |
|---|---|
| Landing + onboarding | `/` |
| Donor registration & profile management | `/donors/register`, `/dashboard/donor` |
| Blood request form (validate → confirm → submit) | `/requests/new` |
| Match results (compatibility, locality, ≈distance, freshness) | `/requests/:id/matches` |
| Request tracking, status transitions, fulfil/cancel with reasons | `/requests/:id` |
| Requester dashboard | `/dashboard/requester` |
| Donor dashboard (availability, contact queue, privacy controls) | `/dashboard/donor` |
| Bridge Assistant (conversational intake, confirmation gate) | `/assistant` |
| WhatsApp-style chat + optional WhatsApp Business Cloud API webhook | `/assistant`, `POST /api/whatsapp/webhook` |
| Community rewards wallet, education modules, coupon catalogue | `/rewards` |
| Referral dashboard (code, link, share, stats, history) | `/referrals` |
| Referral join page (`/join?ref=CODE`) with attribution | `/join` |
| Admin dashboard (stats, moderation, offers, campaigns, review queue, audit) | `/admin` |
| Notifications / activity | bell icon in the top bar + dashboard sections |

### Blood compatibility engine

`backend/app/services/compatibility.py` implements recipient→donor red-cell compatibility
for all eight groups (e.g. O− recipient → O− only; AB+ recipient → all eight). The rules
live **only on the backend** and are tested exhaustively
(`tests/test_compatibility.py`). Matching results always carry the notice:

> "These results support preliminary donor discovery only. Blood transfusion
> compatibility and donor eligibility must be assessed by qualified healthcare
> professionals, including appropriate testing and crossmatching."

### Matching service

`backend/app/services/matching.py` filters candidates by compatibility, active profile,
discoverability consent and availability, then ranks by:

1. Compatibility (exact group scores higher),
2. Geographic proximity (haversine over optional coordinates; city-text match fallback),
3. Current availability,
4. Freshness of the last availability confirmation,
5. Donor preference for urgent requests.

Distance is only displayed when reliable coordinates exist ("distance unavailable"
otherwise — never invented). If nothing matches, the UI shows next steps (expand area,
contact a blood bank). Matching is never presented as a guarantee or as fulfilment.

### Bridge Assistant

- **Deterministic demo mode (default):** a slot-filling flow (blood group → city →
  hospital → units → urgency → needed-by → coordinator → contact → optional notes) with
  validation, re-asking on bad input, FAQ interrupts that don't lose progress, edit
  commands (`edit blood group`), and an explicit confirmation gate — a request is only
  submitted after the user approves (`confirm` / **Approve & submit** button).
- **Optional AI enhancement:** set `BLOODBRIDGE_GEMINI_API_KEY` and the assistant uses a
  Gemini-compatible REST endpoint to extract details from free-form text. Every extracted
  value is re-validated server-side; any API failure/timeout silently falls back to the
  deterministic flow. The key never leaves the backend.
- The assistant never invents donors, availability or medical advice.

### WhatsApp integration

- In-app **WhatsApp-style chat** works fully in Demo Mode and is labelled as a simulation.
- With `BLOODBRIDGE_WHATSAPP_ACCESS_TOKEN` + `BLOODBRIDGE_WHATSAPP_PHONE_NUMBER_ID` set,
  `GET/POST /api/whatsapp/webhook` implements webhook verification, inbound processing
  through the same assistant, outbound delivery via the Graph API, delivery-status
  handling and **message-id deduplication** (at-most-once processing).
- No automation of personal accounts, no scraping. `/api/whatsapp/status` reports the
  active mode.

### Community rewards

Recognition (badges, participation certificates, education records) for profile
verification, education modules, onboarding and community events — **never** for donating
blood, promising to donate, responding to a request or recruiting donors. No cash,
cashback or cash-equivalents (enforced in the service layer). Coupon catalogue entries
carry offer ID, partner, eligibility rules, quantity, validity, redemption instructions
and terms; limited-quantity claims are allocated **transactionally** with duplicate-claim
prevention (DB unique constraint) and full audit logging. Demo partners are always
labelled as fictional. Enabling real-world incentives requires administrator approval and
compliance review against applicable voluntary donation guidelines.

### Referral program

- Unique codes (`BLOODBRIDGE-XXXXX`, DB-enforced uniqueness) + shareable link built from
  `BLOODBRIDGE_APP_BASE_URL` (never hardcoded), copy button, native share, copyable
  invitation message.
- Tracked stages: `link_opened → registration_started → account_created →
  contact_verified → onboarding_completed → referral_reviewed → eligible/rejected`.
  Only measurable events are recorded; per-visit references make tracking idempotent.
- Eligibility: registration + verified contact + completed onboarding + duplicate/abuse
  checks + campaign rules; **never** tied to donation, match acceptance or fulfilment.
- Rewards: badges / certificates / educational recognition only — cash-like types are
  rejected defensively in code and by schema.
- Fraud prevention: one referrer per account, self-referral blocked, identifier-overlap
  flags (phone match, email similarity) route to **human review** (no auto-bans),
  per-user and campaign limits enforced transactionally, rate limiting, audit logs.
- Admin: create campaigns (start as `pending_approval`; activation requires a recorded
  approval note), review queue with reasons, CSV export, audit logs.

---

## API overview

Core: `GET /health`, `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`,
`POST /api/donors`, `GET /api/donors` (admin, masked), `GET/PATCH /api/donors/me`,
`PATCH /api/donors/{id}/availability`, `POST /api/requests`, `GET /api/requests`,
`GET /api/requests/{id}`, `PATCH /api/requests/{id}/status`,
`GET /api/requests/{id}/matches`, `GET /api/requests/{id}/contacts`,
`POST /api/matches/{id}/contact`, `GET /api/contacts/incoming`,
`POST /api/contacts/{id}/respond`, `POST /api/assistant/message`.

Rewards: `GET /api/rewards/offers`, `GET /api/rewards/wallet`,
`POST /api/rewards/offers/{id}/claim`, `GET /api/rewards/history`,
`POST /api/rewards/education/complete`.

Referrals: `GET /api/referrals/me`, `POST /api/referrals/code`, `GET /api/referrals/stats`,
`GET /api/referrals/history`, `GET /api/referrals/campaigns`, `POST /api/referrals/track`,
`POST /api/referrals/attribute`, `POST /api/onboarding/complete`,
`GET /api/notifications`, `POST /api/notifications/read-all`.

Admin (role-checked server-side): `GET /api/admin/stats`, `GET /api/admin/users`,
`GET /api/admin/requests`, `POST /api/admin/donors/{id}/verify`,
`GET/POST /api/admin/offers`, `PATCH /api/admin/offers/{id}`,
`POST /api/admin/claims/{code}/redeem`, `GET /api/admin/referrals`,
`POST /api/admin/referrals/{id}/review`, `GET/POST /api/admin/referrals/campaigns`,
`PATCH /api/admin/referrals/campaigns/{id}`,
`GET /api/admin/referrals/campaigns/{id}/export` (CSV),
`GET /api/admin/audit/rewards`, `GET /api/admin/audit/referrals`.

WhatsApp: `GET/POST /api/whatsapp/webhook`, `GET /api/whatsapp/status`.

Full request/response details: run the server and open **http://127.0.0.1:8000/docs**.

---

## Configuration

Copy `backend/.env.example` to `backend/.env` and adjust. All variables use the
`BLOODBRIDGE_` prefix:

| Variable | Purpose | Default |
|---|---|---|
| `BLOODBRIDGE_DATABASE_URL` | SQLite file, or `postgresql://...` to migrate | `sqlite:///./bloodbridge.db` |
| `BLOODBRIDGE_AUTH_SECRET` | Token signing secret — change in any shared deployment | dev value |
| `BLOODBRIDGE_APP_BASE_URL` | Base URL used to build referral/tracking links | `http://localhost:5173` |
| `BLOODBRIDGE_GEMINI_API_KEY` | Optional AI extraction for the assistant | unset → deterministic demo |
| `BLOODBRIDGE_GEMINI_MODEL` | Model id | `gemini-2.0-flash` |
| `BLOODBRIDGE_WHATSAPP_ACCESS_TOKEN` | WhatsApp Cloud API token | unset → demo mode |
| `BLOODBRIDGE_WHATSAPP_PHONE_NUMBER_ID` | WhatsApp phone number id | unset → demo mode |
| `BLOODBRIDGE_WHATSAPP_VERIFY_TOKEN` | Webhook verification token | `bloodbridge-verify` |
| `BLOODBRIDGE_SEED_DEMO_DATA` | Seed fictional demo data on first boot | `true` |

### Migrating to PostgreSQL

The data layer is SQLAlchemy 2.0 ORM with no SQLite-specific types. Set
`BLOODBRIDGE_DATABASE_URL=postgresql+psycopg://user:pass@host/db`, install a driver
(`pip install psycopg[binary]`), and run `init_db()` (performed automatically at startup).
For schema evolution beyond `create_all`, add Alembic and point it at the same models.

---

## Security & privacy notes

- Passwords: PBKDF2-SHA256 (120k iterations) with per-user salt; sessions are signed
  HMAC tokens with expiry.
- Role-based authorization is enforced **server-side** on every admin/owner endpoint —
  hiding UI controls is never the only gate.
- Donor privacy: phone numbers, exact addresses and precise coordinates are never shown
  publicly. Requesters see blood group, general locality, approximate distance and
  availability. Contact details are revealed only **after a donor accepts** a specific
  contact request (and only if the donor enabled direct contact).
- Guest-created demo requests are tracked by their public id; the public view masks the
  requester's name and hides contact details.
- Rate limiting protects auth, assistant and referral endpoints.

## Project structure

```
bloodbridge/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app + routers + health
│   │   ├── config.py             # env-driven settings
│   │   ├── database.py           # engine/session/init
│   │   ├── security.py           # PBKDF2 + signed tokens + code generation
│   │   ├── models/               # user, donor, request, rewards, referral, misc
│   │   ├── schemas/ (schemas.py) # Pydantic request/response models
│   │   ├── services/             # compatibility, geo, matching, assistant,
│   │   │                         # whatsapp, request/rewards/referral services
│   │   └── routers/              # auth, donors, requests, assistant, whatsapp,
│   │                             # rewards, referrals, account, admin
│   ├── tests/                    # 61 pytest tests
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── pages/                # Landing, Join, Login, DonorRegister, BloodRequest,
    │   │                         # MatchResults, RequesterDashboard, DonorDashboard,
    │   │                         # Rewards, Referrals, Admin, Assistant
    │   ├── components/           # Layout, RequireAuth, UI kit
    │   ├── context/              # AuthContext
    │   ├── utils/validate.ts     # shared client-side validation (unit-tested)
    │   └── tests/                # 10 vitest tests
    └── package.json
```
