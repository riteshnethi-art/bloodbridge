import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { MapPin, RefreshCw, Clock, ShieldCheck, ExternalLink } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import {
  Badge, Button, Card, EmptyState, ErrorText, Notice, PageHeader, Spinner, StatusPill,
} from "../components/ui";
import type { BloodRequest, ContactEvent, Match } from "../types";

function distanceLabel(km: number | null): string {
  if (km === null || km === undefined) return "distance unavailable";
  if (km < 1) return "< 1 km";
  return `≈ ${km.toFixed(1)} km`;
}

function freshness(iso: string | null): string {
  if (!iso) return "unknown";
  const hours = (Date.now() - new Date(iso).getTime()) / 3600000;
  if (hours <= 24) return "confirmed within the last day";
  if (hours <= 24 * 7) return "confirmed within the last week";
  if (hours <= 24 * 30) return "confirmed within the last month";
  return "confirmed over a month ago";
}

export default function MatchResults() {
  const { publicId } = useParams();
  const { user } = useAuth();
  const [request, setRequest] = useState<BloodRequest | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [contacts, setContacts] = useState<ContactEvent[]>([]);
  const [guidance, setGuidance] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [showClose, setShowClose] = useState<"fulfilled" | "cancelled" | null>(null);

  const isOwner = Boolean(user && (request as { created_by?: number } | null)?.created_by === user.id)
    || user?.role === "admin"
    || Boolean(user === null && request); // guest demo requests

  const load = useCallback(async () => {
    if (!publicId) return;
    setLoading(true);
    setError("");
    try {
      const data = await api<{ request: BloodRequest; matches: Match[]; no_match_guidance: string | null }>(
        `/api/requests/${publicId}/matches`,
      );
      setRequest(data.request);
      setMatches(data.matches);
      setGuidance(data.no_match_guidance);
      try {
        const c = await api<{ contacts: ContactEvent[] }>(`/api/requests/${publicId}/contacts`);
        setContacts(c.contacts);
      } catch {
        setContacts([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load request");
    } finally {
      setLoading(false);
    }
  }, [publicId]);

  useEffect(() => {
    load();
  }, [load]);

  const contact = async (matchId: number) => {
    setBusyId(matchId);
    setActionMsg("");
    try {
      const out = await api<{ notice: string }>(`/api/matches/${matchId}/contact`, { body: {} });
      setActionMsg(out.notice);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Contact failed");
    } finally {
      setBusyId(null);
    }
  };

  const close = async (status: "fulfilled" | "cancelled") => {
    if (!publicId || !reason.trim()) return;
    try {
      await api(`/api/requests/${publicId}/status`, { method: "PATCH", body: { status, reason } });
      setShowClose(null);
      setReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  };

  if (loading) return <Spinner label="Loading request..." />;
  if (error && !request) return <ErrorText>{error}</ErrorText>;
  if (!request) return <EmptyState title="Request not found" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Request ${request.public_id}`}
        subtitle={`${request.blood_group} · ${request.units} unit(s) · ${request.hospital}, ${request.locality ? request.locality + ", " : ""}${request.city}`}
        actions={
          <>
            <StatusPill status={request.status} />
            {isOwner && (
              <Button variant="secondary" size="sm" onClick={load}>
                <RefreshCw size={14} /> Refresh matches
              </Button>
            )}
          </>
        }
      />

      {error && <ErrorText>{error}</ErrorText>}
      {actionMsg && <Notice kind="success">{actionMsg}</Notice>}

      <Card className="p-5">
        <div className="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <p className="text-stone-500">Urgency</p>
            <p className="font-medium capitalize">{request.urgency}</p>
          </div>
          <div>
            <p className="text-stone-500">Needed by</p>
            <p className="font-medium">{new Date(request.needed_by).toLocaleString()}</p>
          </div>
          {request.notes && (
            <div className="sm:col-span-2">
              <p className="text-stone-500">Additional information</p>
              <p className="font-medium">{request.notes}</p>
            </div>
          )}
          {request.closed_reason && (
            <div className="sm:col-span-2">
              <p className="text-stone-500">Closed - reason</p>
              <p className="font-medium">{request.closed_reason}</p>
            </div>
          )}
        </div>

        {isOwner && !["fulfilled", "cancelled", "expired"].includes(request.status) && (
          <div className="mt-4 border-t border-stone-100 pt-4">
            {showClose ? (
              <div className="flex flex-wrap items-center gap-2">
                <input
                  className="input-base max-w-sm"
                  placeholder={`Reason to mark ${showClose}...`}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
                <Button size="sm" variant={showClose === "fulfilled" ? "success" : "danger"} onClick={() => close(showClose)}>
                  Confirm {showClose}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setShowClose(null)}>Cancel</Button>
              </div>
            ) : (
              <div className="flex gap-2">
                <Button size="sm" variant="success" onClick={() => setShowClose("fulfilled")}>Mark fulfilled</Button>
                <Button size="sm" variant="secondary" onClick={() => setShowClose("cancelled")}>Cancel request</Button>
              </div>
            )}
            <p className="mt-2 text-xs text-stone-500">
              A request is only fulfilled when blood is actually arranged - finding a donor is not fulfilment.
            </p>
          </div>
        )}
      </Card>

      {/* Contact events */}
      {contacts.length > 0 && (
        <Card className="p-5">
          <h2 className="mb-3 font-semibold">Contact activity</h2>
          <div className="space-y-3">
            {contacts.map((c) => (
              <div key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-stone-100 p-3 text-sm">
                <div>
                  <span className="font-medium">{c.donor?.blood_group}</span> donor ·{" "}
                  <span className="text-stone-500">{c.donor?.locality ? `${c.donor.locality}, ` : ""}{c.donor?.city}</span>
                  {c.donor_contact && (
                    <span className="ml-2 text-emerald-700">Contact: {c.donor_contact}</span>
                  )}
                  {c.donor_message && <p className="text-xs text-stone-500">"{c.donor_message}"</p>}
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill status={c.status} />
                  <span className="text-xs text-stone-400">ref {c.token}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Matches */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Potential donors ({matches.length})</h2>
        {matches.length === 0 ? (
          <EmptyState
            title="No candidate donors right now"
            body={guidance ?? "Try expanding the search area or contacting a hospital blood bank - they maintain live inventory."}
            action={<Link to="/requests/new"><Button variant="secondary" size="sm">Create another request</Button></Link>}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {matches.map((m) => (
              <Card key={m.id} className="p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-lg bg-brand-600 px-2.5 py-1 text-sm font-bold text-white">{m.donor.blood_group}</span>
                      {m.exact_group && <Badge tone="red">exact group</Badge>}
                      {m.donor.verified && <Badge tone="blue"><ShieldCheck size={12} className="mr-1 inline" />verified profile</Badge>}
                    </div>
                    <p className="mt-2 text-sm font-medium text-stone-800">
                      {m.donor.locality ? `${m.donor.locality}, ` : ""}{m.donor.city}
                    </p>
                    <p className="flex items-center gap-1 text-xs text-stone-500">
                      <MapPin size={12} /> {distanceLabel(m.donor.approx_distance_km)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-stone-800">{Math.round(m.score)}/100</p>
                    <p className="text-xs text-stone-400">match score</p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <StatusPill status={m.donor.availability} />
                  <span className="flex items-center gap-1 text-stone-500"><Clock size={12} /> {freshness(m.donor.last_confirmed_at)}</span>
                </div>
                <p className="mt-3 text-xs leading-relaxed text-stone-600">{m.explanation}</p>
                <p className="mt-2 text-xs text-stone-500">
                  Permitted contact: in-app request{m.donor.preferred_contact !== "in_app" ? ` · donor prefers ${m.donor.preferred_contact}` : ""}
                </p>
                {isOwner && request.status !== "fulfilled" && request.status !== "cancelled" && (
                  <Button size="sm" className="mt-3" loading={busyId === m.id} onClick={() => contact(m.id)}>
                    Request contact
                  </Button>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>

      <Notice kind="warning">{request.compatibility_notice}</Notice>

      <p className="text-xs text-stone-500">
        Map context:{" "}
        <a
          className="inline-flex items-center gap-1 text-brand-700 hover:underline"
          target="_blank"
          rel="noreferrer"
          href={`https://www.openstreetmap.org/search?query=${encodeURIComponent(`${request.locality} ${request.city}`)}`}
        >
          view {request.city} on OpenStreetMap <ExternalLink size={11} />
        </a>
      </p>
    </div>
  );
}
