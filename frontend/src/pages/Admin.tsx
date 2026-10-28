import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import {
  Badge, Button, Card, ErrorText, Field, Notice, PageHeader, Spinner, StatusPill,
} from "../components/ui";
import type { BloodRequest, Campaign, RewardOffer } from "../types";

interface Stats {
  users: { total: number; donors: number };
  requests_by_status: Record<string, number>;
  reward_claims: number;
  active_offers: number;
  referrals_by_status: Record<string, number>;
  flagged_referrals: number;
  contact_events: number;
}

interface AdminUser { id: number; name: string; email: string; role: string; email_verified: boolean; onboarding_completed: boolean; created_at: string }
interface AdminDonor { donor_internal_id: number; blood_group: string; city: string; locality: string; availability: string; verified: boolean; masked_contact: string }
interface ReferralRow {
  id: number;
  referrer: { id: number; name: string; email: string } | null;
  referred: { id: number; name: string; email: string } | null;
  status: string;
  source: string;
  flag_reasons: string[];
  attributed_at: string;
  reward: { type: string; status: string } | null;
}
interface AuditRow { id: number; actor_id: number | null; action: string; target_type?: string; target_id: string; reason: string; timestamp: string }

const TABS = ["Overview", "Requests", "Users & donors", "Offers", "Referrals", "Campaigns", "Audit logs"] as const;

export default function Admin() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [stats, setStats] = useState<Stats | null>(null);
  const [requests, setRequests] = useState<BloodRequest[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [donors, setDonors] = useState<AdminDonor[]>([]);
  const [offers, setOffers] = useState<RewardOffer[]>([]);
  const [referrals, setReferrals] = useState<ReferralRow[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [auditR, setAuditR] = useState<AuditRow[]>([]);
  const [auditF, setAuditF] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // offer form
  const [offerForm, setOfferForm] = useState({ partner_name: "", title: "", description: "", quantity: "20" });
  // campaign form
  const [campForm, setCampForm] = useState({ name: "", reward_type: "badge", per_user_limit: "10", total_limit: "200" });
  // rejection reasons
  const [reasons, setReasons] = useState<Record<number, string>>({});

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [s, r, u, d, o, ref, c, ar, af] = await Promise.all([
        api<Stats>("/api/admin/stats"),
        api<{ requests: BloodRequest[] }>("/api/admin/requests"),
        api<{ users: AdminUser[] }>("/api/admin/users"),
        api<{ donors: AdminDonor[] }>("/api/donors"),
        api<{ offers: RewardOffer[] }>("/api/admin/offers"),
        api<{ referrals: ReferralRow[] }>("/api/admin/referrals"),
        api<{ campaigns: Campaign[] }>("/api/admin/referrals/campaigns"),
        api<{ logs: AuditRow[] }>("/api/admin/audit/rewards"),
        api<{ logs: AuditRow[] }>("/api/admin/audit/referrals"),
      ]);
      setStats(s); setRequests(r.requests); setUsers(u.users); setDonors(d.donors);
      setOffers(o.offers); setReferrals(ref.referrals); setCampaigns(c.campaigns);
      setAuditR(ar.logs); setAuditF(af.logs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const act = async (fn: () => Promise<unknown>, successMsg: string) => {
    setError(""); setMessage("");
    try {
      await fn();
      setMessage(successMsg);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  };

  if (loading) return <Spinner label="Loading admin dashboard..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Administrator dashboard"
        subtitle="Platform statistics, moderation, rewards and referral governance."
        actions={<Button variant="secondary" size="sm" onClick={loadAll}>Refresh</Button>}
      />

      <div className="flex flex-wrap gap-1.5">
        {TABS.map((t) => (
          <button key={t}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${tab === t ? "bg-brand-600 text-white" : "bg-white text-stone-600 hover:bg-stone-100 border border-stone-200"}`}
            onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>

      {error && <ErrorText>{error}</ErrorText>}
      {message && <Notice kind="success">{message}</Notice>}

      {tab === "Overview" && stats && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Users", stats.users.total], ["Donor profiles", stats.users.donors],
              ["Reward claims", stats.reward_claims], ["Active offers", stats.active_offers],
            ].map(([l, v]) => (
              <Card key={l as string} className="p-4 text-center">
                <p className="text-2xl font-bold">{v as number}</p>
                <p className="text-xs text-stone-500">{l as string}</p>
              </Card>
            ))}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="p-5">
              <h3 className="font-semibold">Requests by status</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(stats.requests_by_status).length === 0 && <p className="text-sm text-stone-500">No requests yet.</p>}
                {Object.entries(stats.requests_by_status).map(([k, v]) => (
                  <span key={k} className="rounded-full bg-stone-100 px-3 py-1 text-xs">{k.replace(/_/g, " ")}: <strong>{v}</strong></span>
                ))}
              </div>
            </Card>
            <Card className="p-5">
              <h3 className="font-semibold">Referrals by status</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(stats.referrals_by_status).length === 0 && <p className="text-sm text-stone-500">No referrals yet.</p>}
                {Object.entries(stats.referrals_by_status).map(([k, v]) => (
                  <span key={k} className="rounded-full bg-stone-100 px-3 py-1 text-xs">{k}: <strong>{v}</strong></span>
                ))}
              </div>
              {stats.flagged_referrals > 0 && (
                <p className="mt-2 text-xs text-amber-700">{stats.flagged_referrals} flagged for review (no auto-bans).</p>
              )}
            </Card>
          </div>
        </div>
      )}

      {tab === "Requests" && (
        <Card className="divide-y divide-stone-100">
          {requests.length === 0 && <p className="p-4 text-sm text-stone-500">No requests.</p>}
          {requests.map((r) => (
            <div key={r.public_id} className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
              <div>
                <p className="font-medium">{r.public_id} · {r.blood_group} · {r.units}u · {r.hospital}</p>
                <p className="text-xs text-stone-500">{r.city} · {r.urgency} · coordinator {r.requester_name}</p>
              </div>
              <div className="flex items-center gap-2">
                <StatusPill status={r.status} />
                {!["fulfilled", "cancelled", "expired"].includes(r.status) && (
                  <>
                    <Button size="sm" variant="success" onClick={() => act(
                      () => api(`/api/requests/${r.public_id}/status`, { method: "PATCH", body: { status: "fulfilled", reason: "Closed by administrator" } }),
                      `Request ${r.public_id} marked fulfilled.`)}>
                      Fulfil
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => act(
                      () => api(`/api/requests/${r.public_id}/status`, { method: "PATCH", body: { status: "cancelled", reason: "Cancelled by administrator" } }),
                      `Request ${r.public_id} cancelled.`)}>
                      Cancel
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </Card>
      )}

      {tab === "Users & donors" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-5">
            <h3 className="mb-3 font-semibold">Users ({users.length})</h3>
            <div className="max-h-96 space-y-2 overflow-auto">
              {users.map((u) => (
                <div key={u.id} className="flex items-center justify-between rounded-lg border border-stone-100 p-2 text-sm">
                  <div>
                    <p className="font-medium">{u.name}</p>
                    <p className="text-xs text-stone-500">{u.email}</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge tone={u.role === "admin" ? "red" : u.role === "donor" ? "blue" : "neutral"}>{u.role}</Badge>
                    {u.onboarding_completed && <Badge tone="green">onboarded</Badge>}
                  </div>
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <h3 className="mb-3 font-semibold">Donor profiles ({donors.length})</h3>
            <div className="max-h-96 space-y-2 overflow-auto">
              {donors.map((d) => (
                <div key={d.donor_internal_id} className="flex items-center justify-between rounded-lg border border-stone-100 p-2 text-sm">
                  <div>
                    <p className="font-medium">{d.blood_group} · {d.locality ? `${d.locality}, ` : ""}{d.city}</p>
                    <p className="font-mono text-xs text-stone-400">{d.masked_contact}</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <StatusPill status={d.availability} />
                    {d.verified ? <Badge tone="green">verified</Badge> : (
                      <Button size="sm" variant="secondary" onClick={() => act(
                        () => api(`/api/admin/donors/${d.donor_internal_id}/verify`, { body: {} }),
                        "Donor verified - badge issued.")}>
                        Verify
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {tab === "Offers" && (
        <div className="space-y-4">
          <Card className="p-5">
            <h3 className="mb-3 font-semibold">Create offer</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Partner name (prefix with 'Demo Partner:' for fictional partners)">
                <input className="input-base" value={offerForm.partner_name} onChange={(e) => setOfferForm({ ...offerForm, partner_name: e.target.value })} />
              </Field>
              <Field label="Title">
                <input className="input-base" value={offerForm.title} onChange={(e) => setOfferForm({ ...offerForm, title: e.target.value })} />
              </Field>
              <Field label="Description">
                <input className="input-base" value={offerForm.description} onChange={(e) => setOfferForm({ ...offerForm, description: e.target.value })} />
              </Field>
              <Field label="Quantity">
                <input className="input-base" type="number" min={0} value={offerForm.quantity} onChange={(e) => setOfferForm({ ...offerForm, quantity: e.target.value })} />
              </Field>
            </div>
            <Button className="mt-3" onClick={() => act(async () => {
              await api("/api/admin/offers", { body: { ...offerForm, quantity: Number(offerForm.quantity), is_demo_partner: true, status: "active" } });
              setOfferForm({ partner_name: "", title: "", description: "", quantity: "20" });
            }, "Offer created.")}>Create offer</Button>
          </Card>
          <Card className="divide-y divide-stone-100">
            {offers.map((o) => (
              <div key={o.id} className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
                <div>
                  <p className="font-medium">{o.title} <span className="text-xs text-stone-400">({o.offer_ref})</span></p>
                  <p className="text-xs text-stone-500">{o.partner_name} · {o.remaining}/{o.quantity} left</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={o.is_demo_partner ? "amber" : "green"}>{o.partner_label}</Badge>
                  <StatusPill status={o.status} />
                  {o.status === "active" ? (
                    <Button size="sm" variant="secondary" onClick={() => act(
                      () => api(`/api/admin/offers/${o.id}`, { method: "PATCH", body: { status: "paused" } }),
                      "Offer paused.")}>Pause</Button>
                  ) : (
                    <Button size="sm" variant="secondary" onClick={() => act(
                      () => api(`/api/admin/offers/${o.id}`, { method: "PATCH", body: { status: "active" } }),
                      "Offer activated.")}>Activate</Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => act(
                    () => api(`/api/admin/offers/${o.id}`, { method: "PATCH", body: { status: "expired" } }),
                    "Offer expired.")}>Expire</Button>
                </div>
              </div>
            ))}
          </Card>
        </div>
      )}

      {tab === "Referrals" && (
        <Card className="divide-y divide-stone-100">
          {referrals.length === 0 && <p className="p-4 text-sm text-stone-500">No referrals yet.</p>}
          {referrals.map((r) => (
            <div key={r.id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm">
                  <p className="font-medium">{r.referrer?.name} → {r.referred?.name ?? "anonymous visitor"}</p>
                  <p className="text-xs text-stone-500">
                    {r.referrer?.email} → {r.referred?.email ?? "-"} · via {r.source.replace(/_/g, " ")} · {new Date(r.attributed_at).toLocaleString()}
                  </p>
                  {r.flag_reasons.length > 0 && (
                    <p className="text-xs text-amber-700">Flags: {r.flag_reasons.join(", ")}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {r.reward && <Badge tone="green">{r.reward.type} · {r.reward.status}</Badge>}
                  <StatusPill status={r.status} />
                  {["pending", "under_review", "eligible"].includes(r.status) && (
                    <>
                      <Button size="sm" variant="success" onClick={() => act(
                        () => api(`/api/admin/referrals/${r.id}/review`, { body: { approve: true, reason: "" } }),
                        "Referral approved and reward issued.")}>
                        Approve
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => {
                        const reason = reasons[r.id] ?? "";
                        if (!reason.trim()) { setError("A rejection reason is required."); return; }
                        act(() => api(`/api/admin/referrals/${r.id}/review`, { body: { approve: false, reason } }),
                          "Referral rejected with reason recorded.");
                      }}>
                        Reject
                      </Button>
                      <input className="input-base w-44" placeholder="Rejection reason"
                             value={reasons[r.id] ?? ""}
                             onChange={(e) => setReasons({ ...reasons, [r.id]: e.target.value })} />
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </Card>
      )}

      {tab === "Campaigns" && (
        <div className="space-y-4">
          <Card className="p-5">
            <h3 className="mb-3 font-semibold">Create campaign (starts as pending approval)</h3>
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Name">
                <input className="input-base" value={campForm.name} onChange={(e) => setCampForm({ ...campForm, name: e.target.value })} />
              </Field>
              <Field label="Reward type" hint="Non-cash only">
                <select className="input-base" value={campForm.reward_type} onChange={(e) => setCampForm({ ...campForm, reward_type: e.target.value })}>
                  <option value="badge">Badge</option>
                  <option value="certificate">Certificate</option>
                  <option value="educational">Educational</option>
                </select>
              </Field>
              <Field label="Per-user limit">
                <input className="input-base" type="number" min={1} value={campForm.per_user_limit} onChange={(e) => setCampForm({ ...campForm, per_user_limit: e.target.value })} />
              </Field>
              <Field label="Total limit">
                <input className="input-base" type="number" min={1} value={campForm.total_limit} onChange={(e) => setCampForm({ ...campForm, total_limit: e.target.value })} />
              </Field>
            </div>
            <Button className="mt-3" onClick={() => act(async () => {
              await api("/api/admin/referrals/campaigns", {
                body: {
                  ...campForm,
                  per_user_limit: Number(campForm.per_user_limit),
                  total_limit: Number(campForm.total_limit),
                  description: "Created from admin dashboard.",
                  terms: "Non-cash recognition only. Never conditional on blood donation.",
                },
              });
              setCampForm({ name: "", reward_type: "badge", per_user_limit: "10", total_limit: "200" });
            }, "Campaign created as pending approval.")}>Create campaign</Button>
          </Card>
          <Card className="divide-y divide-stone-100">
            {campaigns.map((c) => (
              <div key={c.id} className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
                <div>
                  <p className="font-medium">{c.name}</p>
                  <p className="text-xs text-stone-500">
                    reward: {c.reward_type} · eligible event: {c.eligible_event.replace(/_/g, " ")}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill status={c.status} />
                  {c.status !== "active" && c.status !== "ended" && (
                    <Button size="sm" variant="success" onClick={() => {
                      const note = window.prompt("Approval note (compliance review) required to activate:");
                      if (!note?.trim()) { setError("Activation requires an approval note."); return; }
                      act(() => api(`/api/admin/referrals/campaigns/${c.id}`, { method: "PATCH", body: { status: "active", approval_note: note } }),
                        "Campaign activated with recorded approval.");
                    }}>
                      Activate
                    </Button>
                  )}
                  {c.status === "active" && (
                    <Button size="sm" variant="secondary" onClick={() => act(
                      () => api(`/api/admin/referrals/campaigns/${c.id}`, { method: "PATCH", body: { status: "paused" } }),
                      "Campaign paused.")}>Pause</Button>
                  )}
                  <a href={`/api/admin/referrals/campaigns/${c.id}/export`} className="text-xs text-brand-700 underline">Export CSV</a>
                </div>
              </div>
            ))}
          </Card>
        </div>
      )}

      {tab === "Audit logs" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-5">
            <h3 className="mb-3 font-semibold">Rewards audit</h3>
            <div className="max-h-96 space-y-1.5 overflow-auto text-xs">
              {auditR.map((l) => (
                <div key={l.id} className="rounded border border-stone-100 p-2">
                  <span className="font-mono text-stone-400">{new Date(l.timestamp).toLocaleString()}</span> · <strong>{l.action}</strong> {l.target_type} {l.target_id} {l.reason && `· ${l.reason}`}
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <h3 className="mb-3 font-semibold">Referral audit</h3>
            <div className="max-h-96 space-y-1.5 overflow-auto text-xs">
              {auditF.map((l) => (
                <div key={l.id} className="rounded border border-stone-100 p-2">
                  <span className="font-mono text-stone-400">{new Date(l.timestamp).toLocaleString()}</span> · <strong>{l.action}</strong> #{l.target_id} {l.reason && `· ${l.reason}`}
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
