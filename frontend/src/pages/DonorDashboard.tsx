import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Power, RefreshCw } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import {
  Badge, Button, Card, EmptyState, ErrorText, Field, Notice, PageHeader, Spinner, StatusPill,
} from "../components/ui";
import { BLOOD_GROUPS } from "../utils/validate";
import type { ContactEvent, DonorProfile } from "../types";

export default function DonorDashboard() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<DonorProfile | null>(null);
  const [contacts, setContacts] = useState<ContactEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    blood_group: "", city: "", locality: "", preferred_contact: "in_app",
    availability: "available", discoverable: true, allow_direct_contact: false,
    can_receive_urgent: true, lat: "", lng: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      try {
        const p = await api<DonorProfile>("/api/donors/me");
        setProfile(p);
        setForm({
          blood_group: p.blood_group, city: p.city, locality: p.locality,
          preferred_contact: p.preferred_contact, availability: p.availability,
          discoverable: p.discoverable, allow_direct_contact: p.allow_direct_contact,
          can_receive_urgent: p.can_receive_urgent, lat: "", lng: "",
        });
      } catch {
        setProfile(null);
      }
      const c = await api<{ contacts: ContactEvent[] }>("/api/contacts/incoming");
      setContacts(c.contacts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load donor dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const body = {
        blood_group: form.blood_group, city: form.city, locality: form.locality,
        preferred_contact: form.preferred_contact, availability: form.availability,
        discoverable: form.discoverable, allow_direct_contact: form.allow_direct_contact,
        can_receive_urgent: form.can_receive_urgent,
        lat: form.lat ? Number(form.lat) : null, lng: form.lng ? Number(form.lng) : null,
      };
      const saved = profile
        ? await api<DonorProfile>("/api/donors/me", { method: "PATCH", body })
        : await api<DonorProfile>("/api/donors", { body });
      setProfile(saved);
      setMessage("Profile saved. Availability timestamp refreshed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const quickAvailability = async (value: string) => {
    if (!profile) return;
    setBusy(true);
    try {
      const updated = await api<DonorProfile>(`/api/donors/${profile.id}/availability`, {
        method: "PATCH", body: { availability: value },
      });
      setProfile(updated);
      setMessage(`Availability set to ${value}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  };

  const respond = async (id: number, accept: boolean) => {
    setBusy(true);
    try {
      await api(`/api/contacts/${id}/respond`, { body: { accept, message: "" } });
      setMessage(accept ? "Contact accepted - the requester has been notified." : "Contact declined.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Response failed");
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Spinner label="Loading donor dashboard..." />;

  return (
    <div className="space-y-8">
      <PageHeader
        title={`Donor hub - ${user?.name}`}
        subtitle="Manage your profile, availability and incoming contact requests."
        actions={
          <>
            {profile && (
              <Link to="/rewards"><Button variant="secondary" size="sm">Rewards & certificates</Button></Link>
            )}
            <Link to="/referrals"><Button variant="secondary" size="sm">Referrals</Button></Link>
          </>
        }
      />

      {error && <ErrorText>{error}</ErrorText>}
      {message && <Notice kind="success">{message}</Notice>}

      {!profile ? (
        <EmptyState
          title="No donor profile yet"
          body="Create your donor profile to appear in match results. You control discoverability and contact preferences."
          action={<Link to="/donors/register"><Button size="sm">Create donor profile</Button></Link>}
        />
      ) : (
        <>
          <Card className="p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="rounded-lg bg-brand-600 px-3 py-1.5 text-lg font-bold text-white">{profile.blood_group}</span>
                <div>
                  <p className="text-sm font-medium">{profile.locality ? `${profile.locality}, ` : ""}{profile.city}</p>
                  <p className="text-xs text-stone-500">
                    Availability confirmed {profile.last_confirmed_at ? new Date(profile.last_confirmed_at).toLocaleString() : "unknown"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusPill status={profile.availability} />
                {profile.verified && <Badge tone="blue">verified profile</Badge>}
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 border-t border-stone-100 pt-4">
              <Button size="sm" variant="secondary" loading={busy} onClick={() => quickAvailability("available")}>
                <RefreshCw size={14} /> I'm available
              </Button>
              <Button size="sm" variant="secondary" loading={busy} onClick={() => quickAvailability("maybe")}>
                Maybe
              </Button>
              <Button size="sm" variant="secondary" loading={busy} onClick={() => quickAvailability("unavailable")}>
                <Power size={14} /> Pause (unavailable)
              </Button>
            </div>
          </Card>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Incoming contact requests ({contacts.length})</h2>
            {contacts.length === 0 ? (
              <EmptyState
                title="No contact requests right now"
                body="When a nearby requester with a compatible blood group initiates permitted contact, it appears here for you to accept or decline."
              />
            ) : (
              <div className="space-y-3">
                {contacts.map((c) => (
                  <Card key={c.id} className="p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-brand-50 px-2 py-0.5 text-sm font-bold text-brand-700">{c.blood_group}</span>
                          <StatusPill status={c.urgency} />
                          <StatusPill status={c.status} />
                        </div>
                        <p className="mt-2 text-sm font-medium">{c.hospital}</p>
                        <p className="text-sm text-stone-500">{c.locality ? `${c.locality}, ` : ""}{c.city} · {c.units} unit(s) · needed by {new Date(c.needed_by).toLocaleString()}</p>
                        {c.requester_name && <p className="mt-1 text-xs text-stone-500">Coordinator: {c.requester_name} · {c.requester_contact_method}: {c.requester_contact}</p>}
                        <p className="mt-1 text-xs text-stone-400">Reference {c.token}</p>
                      </div>
                      {c.status === "initiated" && (
                        <div className="flex gap-2">
                          <Button size="sm" variant="success" loading={busy} onClick={() => respond(c.id, true)}>Accept</Button>
                          <Button size="sm" variant="secondary" loading={busy} onClick={() => respond(c.id, false)}>Decline</Button>
                        </div>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Profile & privacy controls</h2>
            <Card className="p-6">
              <form onSubmit={saveProfile} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Blood group">
                    <select className="input-base" value={form.blood_group} onChange={(e) => setForm({ ...form, blood_group: e.target.value })}>
                      {BLOOD_GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}
                    </select>
                  </Field>
                  <Field label="Availability">
                    <select className="input-base" value={form.availability} onChange={(e) => setForm({ ...form, availability: e.target.value })}>
                      <option value="available">Available</option>
                      <option value="maybe">Maybe</option>
                      <option value="unavailable">Unavailable</option>
                    </select>
                  </Field>
                  <Field label="City">
                    <input className="input-base" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
                  </Field>
                  <Field label="Locality">
                    <input className="input-base" value={form.locality} onChange={(e) => setForm({ ...form, locality: e.target.value })} />
                  </Field>
                  <Field label="Preferred contact method">
                    <select className="input-base" value={form.preferred_contact} onChange={(e) => setForm({ ...form, preferred_contact: e.target.value })}>
                      <option value="in_app">In-app only</option>
                      <option value="email">Email</option>
                      <option value="phone">Phone</option>
                      <option value="whatsapp">WhatsApp</option>
                    </select>
                  </Field>
                  <Field label="Optional coordinates" hint="Used only for approximate distance. Never displayed.">
                    <div className="flex gap-2">
                      <input className="input-base" value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} placeholder="Lat" />
                      <input className="input-base" value={form.lng} onChange={(e) => setForm({ ...form, lng: e.target.value })} placeholder="Lng" />
                    </div>
                  </Field>
                </div>
                <div className="space-y-2.5 rounded-lg border border-stone-200 p-4">
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-0.5" checked={form.discoverable} onChange={(e) => setForm({ ...form, discoverable: e.target.checked })} />
                    <span><strong>Discoverable</strong> - appear in match results (you can pause anytime).</span>
                  </label>
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-0.5" checked={form.allow_direct_contact} onChange={(e) => setForm({ ...form, allow_direct_contact: e.target.checked })} />
                    <span><strong>Share contact after accepting</strong> - otherwise coordination stays in-app.</span>
                  </label>
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-0.5" checked={form.can_receive_urgent} onChange={(e) => setForm({ ...form, can_receive_urgent: e.target.checked })} />
                    <span><strong>Open to urgent requests</strong>.</span>
                  </label>
                </div>
                <Button type="submit" loading={busy}>Save profile</Button>
              </form>
            </Card>
          </section>
        </>
      )}
    </div>
  );
}
