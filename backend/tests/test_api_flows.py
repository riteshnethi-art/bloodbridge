"""End-to-end API workflow tests over HTTP (TestClient)."""
from __future__ import annotations

from datetime import timedelta

from app.database import SessionLocal, utcnow


def _future(hours: int = 26) -> str:
    return (utcnow() + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")


def _register(client, email: str, role: str = "requester", referral: str | None = None):
    payload = {
        "name": email.split("@")[0].title(), "email": email,
        "password": "passw0rd123", "role": role, "privacy_accepted": True,
    }
    if referral:
        payload["referral_code"] = referral
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "compatibility_notice" in resp.json()


def test_register_login_me(client):
    headers, user = _register(client, "flow1@test.demo")
    assert user["email"] == "flow1@test.demo"
    login = client.post("/api/auth/login",
                        json={"email": "flow1@test.demo", "password": "passw0rd123"})
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "flow1@test.demo"
    bad = client.post("/api/auth/login",
                      json={"email": "flow1@test.demo", "password": "wrong-password"})
    assert bad.status_code == 401


def test_donor_profile_and_privacy(client):
    headers, _ = _register(client, "flowdonor1@test.demo", role="donor")
    created = client.post("/api/donors", headers=headers, json={
        "blood_group": "O-", "city": "Hyderabad", "locality": "Gachibowli",
        "lat": 17.44, "lng": 78.35, "preferred_contact": "in_app",
        "availability": "available", "discoverable": True,
        "allow_direct_contact": False, "can_receive_urgent": True,
    })
    assert created.status_code == 200, created.text
    donor = created.json()
    assert donor["availability"] == "available"

    # Availability update
    patched = client.patch(f"/api/donors/{donor['id']}/availability", headers=headers,
                           json={"availability": "maybe"})
    assert patched.status_code == 200
    assert patched.json()["availability"] == "maybe"

    # Donor directory is admin-only
    forbidden = client.get("/api/donors", headers=headers)
    assert forbidden.status_code == 403


def test_full_request_to_contact_flow(client):
    donor_headers, _ = _register(client, "flowdonor2@test.demo", role="donor")
    client.post("/api/donors", headers=donor_headers, json={
        "blood_group": "B+", "city": "Hyderabad", "locality": "Gachibowli",
        "preferred_contact": "in_app", "availability": "available",
        "discoverable": True, "allow_direct_contact": False,
        "can_receive_urgent": True,
    })
    req_headers, _ = _register(client, "flowreq1@test.demo")

    # Validation failure first
    bad = client.post("/api/requests", headers=req_headers, json={
        "blood_group": "B+", "city": "Hyderabad", "hospital": "Demo Hospital",
        "units": 0, "urgency": "urgent", "needed_by": _future(),
        "requester_name": "Flow Requester", "contact_value": "+919999911111",
    })
    assert bad.status_code == 422

    created = client.post("/api/requests", headers=req_headers, json={
        "blood_group": "B+", "city": "Hyderabad", "locality": "Gachibowli",
        "hospital": "Demo Multispeciality Hospital", "units": 2,
        "urgency": "urgent", "needed_by": _future(),
        "requester_name": "Flow Requester", "contact_value": "+919999911111",
        "contact_method": "phone", "notes": "",
    })
    assert created.status_code == 200, created.text
    body = created.json()
    public_id = body["request"]["public_id"]
    assert public_id.startswith("BB-")

    matches = client.get(f"/api/requests/{public_id}/matches", headers=req_headers)
    assert matches.status_code == 200
    match_list = matches.json()["matches"]
    assert len(match_list) >= 1
    assert match_list[0]["donor"]["blood_group"] == "B+"
    assert "qualified healthcare professionals" in matches.json()["request"]["compatibility_notice"]

    # Public tracking view hides contact details
    public = client.get(f"/api/requests/{public_id}")
    assert public.status_code == 200
    assert "contact_value" not in public.json()

    # Initiate contact -> donor accepts
    match_id = match_list[0]["id"]
    contact = client.post(f"/api/matches/{match_id}/contact", headers=req_headers,
                          json={"method": "in_app"})
    assert contact.status_code == 200
    assert contact.json()["contact"]["status"] == "initiated"

    incoming = client.get("/api/contacts/incoming", headers=donor_headers)
    assert incoming.status_code == 200
    assert len(incoming.json()["contacts"]) == 1
    event_id = incoming.json()["contacts"][0]["id"]

    accepted = client.post(f"/api/contacts/{event_id}/respond", headers=donor_headers,
                           json={"accept": True, "message": "I can come tomorrow."})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    detail = client.get(f"/api/requests/{public_id}", headers=req_headers)
    assert detail.json()["status"] == "donor_responded"

    # Invalid transition: fulfilled -> pending must fail
    invalid = client.patch(f"/api/requests/{public_id}/status", headers=req_headers,
                           json={"status": "pending"})
    assert invalid.status_code == 422

    # Fulfil requires a reason
    no_reason = client.patch(f"/api/requests/{public_id}/status", headers=req_headers,
                             json={"status": "fulfilled"})
    assert no_reason.status_code == 422
    fulfilled = client.patch(f"/api/requests/{public_id}/status", headers=req_headers,
                             json={"status": "fulfilled", "reason": "Units received at hospital"})
    assert fulfilled.status_code == 200
    assert fulfilled.json()["status"] == "fulfilled"


def test_request_owner_authorization(client):
    owner_headers, _ = _register(client, "flowowner@test.demo")
    other_headers, _ = _register(client, "flowother@test.demo")
    created = client.post("/api/requests", headers=owner_headers, json={
        "blood_group": "A+", "city": "Pune", "hospital": "Demo Hospital East",
        "units": 1, "urgency": "routine", "needed_by": _future(72),
        "requester_name": "Owner One", "contact_value": "owner1@test.demo",
        "contact_method": "email",
    })
    public_id = created.json()["request"]["public_id"]
    # Another user cannot view matches or change status
    assert client.get(f"/api/requests/{public_id}/matches",
                      headers=other_headers).status_code == 403
    assert client.patch(f"/api/requests/{public_id}/status", headers=other_headers,
                        json={"status": "cancelled"}).status_code == 403
    # Owner can cancel with reason
    ok = client.patch(f"/api/requests/{public_id}/status", headers=owner_headers,
                      json={"status": "cancelled", "reason": "Arranged via blood bank"})
    assert ok.status_code == 200


def test_rewards_claim_flow(client, admin_headers):
    # Create a demo offer via the admin API (test DB starts empty).
    created = client.post("/api/admin/offers", headers=admin_headers, json={
        "partner_name": "Demo Partner: FlowMart", "title": "Flow Voucher",
        "description": "Test voucher", "quantity": 5, "status": "active",
    })
    assert created.status_code == 200
    offers = client.get("/api/rewards/offers")
    assert offers.status_code == 200
    assert len(offers.json()["offers"]) >= 1
    assert any("Demo Partner" in o["partner_label"] for o in offers.json()["offers"])
    offer = next(o for o in offers.json()["offers"] if o["title"] == "Flow Voucher")

    headers, _ = _register(client, "flowreward@test.demo")
    claim = client.post(f"/api/rewards/offers/{offer['id']}/claim", headers=headers)
    assert claim.status_code == 200
    code = claim.json()["claim_code"]
    assert code.startswith("CLM-")

    dup = client.post(f"/api/rewards/offers/{offer['id']}/claim", headers=headers)
    assert dup.status_code == 422

    history = client.get("/api/rewards/history", headers=headers)
    assert history.status_code == 200
    assert history.json()["claim_count"] == 1

    edu = client.post("/api/rewards/education/complete", headers=headers,
                      json={"module_key": "donation_basics"})
    assert edu.status_code == 200
    assert edu.json()["recognition"]["reference"].startswith("REC-")

    wallet = client.get("/api/rewards/wallet", headers=headers)
    assert wallet.status_code == 200
    assert len(wallet.json()["education"]) == 1


def test_referral_flow_end_to_end(client, admin_headers):
    # An active campaign must exist for eligibility evaluation.
    campaign = client.post("/api/admin/referrals/campaigns", headers=admin_headers, json={
        "name": "E2E Campaign", "reward_type": "badge",
        "per_user_limit": 10, "total_limit": 100,
    })
    assert campaign.status_code == 200
    cid = campaign.json()["id"]
    activated = client.patch(f"/api/admin/referrals/campaigns/{cid}", headers=admin_headers,
                             json={"status": "active", "approval_note": "Demo compliance review"})
    assert activated.status_code == 200

    # Public campaign listing shows active campaigns with terms
    public = client.get("/api/referrals/campaigns")
    assert public.status_code == 200
    assert any(c["name"] == "E2E Campaign" for c in public.json()["campaigns"])

    # Referrer signs up and gets a code
    ref_headers, _ = _register(client, "flowref@test.demo")
    me = client.get("/api/referrals/me", headers=ref_headers)
    assert me.status_code == 200
    code = me.json()["code"]
    assert code.startswith("BLOODBRIDGE-")
    assert "/join?ref=" in me.json()["link"]

    # Anonymous tracking of link_opened on the /join page (per-visit reference)
    tracked = client.post("/api/referrals/track",
                          json={"code": code, "event_type": "link_opened",
                                "reference": "visit-abc-1"})
    assert tracked.status_code == 200
    assert tracked.json()["recorded"] is True
    dup_track = client.post("/api/referrals/track",
                            json={"code": code, "event_type": "link_opened",
                                  "reference": "visit-abc-1"})
    assert dup_track.json()["recorded"] is False  # idempotent per visit reference
    # A different visit counts as a new measurable open
    client.post("/api/referrals/track",
                json={"code": code, "event_type": "link_opened", "reference": "visit-abc-2"})

    # New user registers with the code
    new_headers, new_user = _register(client, "flownew@test.demo", referral=code)
    stats = client.get("/api/referrals/stats", headers=ref_headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["registrations"] == 1
    assert body["link_visits_measured"] == 2

    # New user completes onboarding -> referral goes to review
    onboarding = client.post("/api/onboarding/complete", headers=new_headers)
    assert onboarding.status_code == 200
    assert onboarding.json()["referral"]["attributed"] is True
    assert onboarding.json()["referral"]["status"] == "under_review"

    history = client.get("/api/referrals/history", headers=ref_headers)
    assert history.status_code == 200
    referrals = history.json()["referrals"]
    assert len(referrals) == 1
    event_types = [e["type"] for e in referrals[0]["events"]]
    assert "account_created" in event_types
    assert "onboarding_completed" in event_types

    # Not approved yet - no reward displayed as approved
    assert referrals[0]["status"] == "under_review"
    assert referrals[0]["reward"] is None


def test_admin_dashboard_and_review(client, admin_headers):
    # An active campaign must exist before referrals can be reviewed.
    campaign = client.post("/api/admin/referrals/campaigns", headers=admin_headers, json={
        "name": "Review Queue Campaign", "reward_type": "badge",
        "per_user_limit": 10, "total_limit": 100,
    })
    assert campaign.status_code == 200
    cid = campaign.json()["id"]
    client.patch(f"/api/admin/referrals/campaigns/{cid}", headers=admin_headers,
                 json={"status": "active", "approval_note": "Demo compliance review"})

    # Create a referral that needs review
    ref_headers, _ = _register(client, "adminref@test.demo")
    code = client.get("/api/referrals/me", headers=ref_headers).json()["code"]
    new_headers, _ = _register(client, "adminnew@test.demo", referral=code)
    client.post("/api/onboarding/complete", headers=new_headers)

    # Non-admin blocked
    assert client.get("/api/admin/stats").status_code in (401, 403)
    stats = client.get("/api/admin/stats", headers=admin_headers)
    assert stats.status_code == 200
    assert "referrals_by_status" in stats.json()

    queue = client.get("/api/admin/referrals", headers=admin_headers)
    assert queue.status_code == 200
    target = next(r for r in queue.json()["referrals"]
                  if r["status"] == "under_review"
                  and r["referrer"] and r["referrer"]["email"] == "adminref@test.demo")

    # Approve without reason is fine; rejection requires reason
    approved = client.post(f"/api/admin/referrals/{target['id']}/review",
                           headers=admin_headers, json={"approve": True, "reason": ""})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    # Reward visible to referrer
    ref_stats = client.get("/api/referrals/stats", headers=ref_headers)
    assert ref_stats.json()["approved"] == 1

    # Campaign management
    campaigns = client.get("/api/admin/referrals/campaigns", headers=admin_headers)
    assert campaigns.status_code == 200
    created = client.post("/api/admin/referrals/campaigns", headers=admin_headers, json={
        "name": "Test Drive Campaign", "reward_type": "certificate",
        "per_user_limit": 3, "total_limit": 50,
    })
    assert created.status_code == 200
    assert created.json()["status"] == "pending_approval"
    cid = created.json()["id"]
    # Activation without approval note fails
    no_note = client.patch(f"/api/admin/referrals/campaigns/{cid}", headers=admin_headers,
                           json={"status": "active"})
    assert no_note.status_code == 422
    activated = client.patch(f"/api/admin/referrals/campaigns/{cid}", headers=admin_headers,
                             json={"status": "active",
                                   "approval_note": "Compliance review done for demo"})
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    # Audit logs
    logs = client.get("/api/admin/audit/referrals", headers=admin_headers)
    assert logs.status_code == 200
    assert len(logs.json()["logs"]) >= 1


def test_assistant_endpoint_flow(client):
    session = "test-assistant-1"
    r1 = client.post("/api/assistant/message",
                     json={"session_id": session, "message": "O negative"})
    assert r1.status_code == 200
    assert r1.json()["awaiting"] == "slot"
    # Finish the flow
    for msg in ["Hyderabad", "Demo Hospital", "1", "urgent", "tomorrow",
                "Assistant Tester", "+919812341234", "skip", "skip"]:
        resp = client.post("/api/assistant/message",
                           json={"session_id": session, "message": msg})
    assert resp.json()["awaiting"] == "confirm"
    submitted = client.post("/api/assistant/message",
                            json={"session_id": session, "message": "confirm"})
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["done"] is True
    assert body["request_public_id"].startswith("BB-")
    # The request exists and is viewable
    detail = client.get(f"/api/requests/{body['request_public_id']}")
    assert detail.status_code == 200
    assert detail.json()["blood_group"] == "O-"


def test_whatsapp_demo_mode(client):
    status = client.get("/api/whatsapp/status")
    assert status.status_code == 200
    assert status.json()["demo"] is True

    verify = client.get("/api/whatsapp/webhook",
                        params={"hub.mode": "subscribe",
                                "hub.verify_token": "bloodbridge-verify",
                                "hub.challenge": "12345"})
    assert verify.status_code == 200
    assert verify.text == "12345"

    bad = client.get("/api/whatsapp/webhook",
                     params={"hub.mode": "subscribe", "hub.verify_token": "wrong",
                             "hub.challenge": "12345"})
    assert bad.status_code == 403

    inbound = client.post("/api/whatsapp/webhook", json={
        "entry": [{"changes": [{"value": {"messages": [{
            "id": "wamid.test1", "from": "919999988888", "type": "text",
            "text": {"body": "hello"},
        }]}}]}]})
    assert inbound.status_code == 200
    assert inbound.json()["received"] is True
    # Demo mode: nothing delivered externally, reply simulated
    assert inbound.json()["replies"][0]["send"]["delivered"] is False

    # Deduplication: same message id processed once
    repeat = client.post("/api/whatsapp/webhook", json={
        "entry": [{"changes": [{"value": {"messages": [{
            "id": "wamid.test1", "from": "919999988888", "type": "text",
            "text": {"body": "hello again"},
        }]}}]}]})
    assert repeat.json()["duplicates_skipped"] == 1
    assert repeat.json()["replies"] == []


def test_admin_offer_management(client, admin_headers):
    created = client.post("/api/admin/offers", headers=admin_headers, json={
        "partner_name": "Demo Partner: TestMart", "title": "Test Voucher",
        "description": "d", "quantity": 5, "status": "active",
    })
    assert created.status_code == 200
    offer = created.json()
    assert offer["is_demo_partner"] is True

    paused = client.patch(f"/api/admin/offers/{offer['id']}", headers=admin_headers,
                          json={"status": "paused"})
    assert paused.json()["status"] == "paused"

    # Quantity below claimed count is rejected
    user_headers, _ = _register(client, "offerclaim@test.demo")
    client.patch(f"/api/admin/offers/{offer['id']}", headers=admin_headers,
                 json={"status": "active"})
    client.post(f"/api/rewards/offers/{offer['id']}/claim", headers=user_headers)
    too_low = client.patch(f"/api/admin/offers/{offer['id']}", headers=admin_headers,
                           json={"quantity": 0})
    assert too_low.status_code == 422
