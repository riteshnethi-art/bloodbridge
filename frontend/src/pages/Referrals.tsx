import { useCallback, useEffect, useState } from "react";
import { Check, Copy, MessageCircle, Share2, Users } from "lucide-react";
import { api } from "../api";
import {
  Badge, Button, Card, EmptyState, ErrorText, Notice, PageHeader, Spinner, StatusPill,
} from "../components/ui";
import type { Campaign, ReferralHistoryItem, ReferralStats } from "../types";

interface MeResponse {
  code: string;
  link: string;
  invitation_message: string;
  disclaimer: string;
}

export default function Referrals() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [history, setHistory] = useState<{ referrals: ReferralHistoryItem[]; pre_registration_events: { type: string; at: string }[] } | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, s, h, c] = await Promise.all([
        api<MeResponse>("/api/referrals/me"),
        api<ReferralStats>("/api/referrals/stats"),
        api<{ referrals: ReferralHistoryItem[]; pre_registration_events: { type: string; at: string }[] }>("/api/referrals/history"),
        api<{ campaigns: Campaign[] }>("/api/referrals/campaigns"),
      ]);
      setMe(m);
      setStats(s);
      setHistory(h);
      setCampaigns(c.campaigns);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load referrals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const copyText = async (text: string, tag: string) => {
    try {
      if (navigator.clipboard) await navigator.clipboard.writeText(text);
      setCopied(tag);
      setTimeout(() => setCopied(""), 1500);
    } catch {
      setError("Copy failed - select the text manually.");
    }
  };

  const share = async () => {
    if (!me) return;
    if (navigator.share) {
      try {
        await navigator.share({ title: "Join BloodBridge", text: me.invitation_message, url: me.link });
      } catch {
        /* user cancelled */
      }
    } else {
      copyText(me.link, "link");
    }
  };

  const shareWhatsApp = () => {
    if (!me) return;
    // Opens WhatsApp (app or web) with the invitation pre-filled - nothing is sent by us.
    const url = `https://wa.me/?text=${encodeURIComponent(me.invitation_message)}`;
    window.open(url, "_blank", "noopener");
  };

  if (loading) return <Spinner label="Loading referral dashboard..." />;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Community invites"
        subtitle="Invite friends to grow the community - earn the Community Connector badge when someone you invited completes onboarding. Non-cash, never tied to blood donation."
      />

      {error && <ErrorText>{error}</ErrorText>}

      {/* Invite card */}
      {me && (
        <Card className="p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm text-stone-500">Your unique referral code</p>
              <p className="font-mono text-xl font-bold text-brand-700">{me.code}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" onClick={() => copyText(me.link, "link")}>
                {copied === "link" ? <Check size={14} /> : <Copy size={14} />} Copy invite link
              </Button>
              <Button size="sm" variant="secondary" onClick={shareWhatsApp}>
                <MessageCircle size={14} /> WhatsApp
              </Button>
              <Button size="sm" onClick={share}>
                <Share2 size={14} /> Share
              </Button>
            </div>
          </div>
          <div className="mt-4 rounded-lg bg-stone-50 p-3">
            <p className="text-xs text-stone-500">Invitation message</p>
            <p className="mt-1 text-sm text-stone-700">{me.invitation_message}</p>
            <Button size="sm" variant="ghost" className="mt-2" onClick={() => copyText(me.invitation_message, "msg")}>
              {copied === "msg" ? <Check size={14} /> : <Copy size={14} />} Copy message
            </Button>
          </div>
          <p className="mt-3 text-xs text-stone-500">{me.disclaimer}</p>
        </Card>
      )}

      {/* Milestone stepper - how an invite becomes a badge */}
      {stats && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">How an invite becomes a badge</h2>
          <Card className="p-5">
            <div className="flex flex-wrap items-center gap-2">
              {[
                ["Invite ready", true, "your code is active"],
                ["Friend registers", stats.registrations > 0, `${stats.registrations} so far`],
                ["Contact verified", stats.contact_verified > 0, `${stats.contact_verified} so far`],
                ["Badge approved", stats.approved > 0, `${stats.approved} earned`],
              ].map(([label, done, hint], i) => (
                <div key={label as string} className="flex items-center gap-2">
                  {i > 0 && <span className="text-stone-300" aria-hidden>&rarr;</span>}
                  <div className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${done ? "border-green-300 bg-green-50 text-green-800" : "border-stone-200 bg-stone-50 text-stone-500"}`}>
                    <span className={`inline-block h-2 w-2 rounded-full ${done ? "bg-green-500" : "bg-stone-300"}`} />
                    {label as string}
                    <span className="text-[10px] font-normal opacity-75">{hint as string}</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-sm text-stone-600">
              {stats.approved > 0
                ? "Badge earned - thank you for growing the community."
                : stats.contact_verified > 0
                  ? "Your friend is fully verified - the final step is an admin review, then the badge is yours."
                  : stats.registrations > 0
                    ? "Your invite is working - the next milestone unlocks when your friend's contact is verified."
                    : "Share your invite link or tap WhatsApp above - a friend joining through your code is step one."}
            </p>
            <p className="mt-1 text-xs text-stone-400">
              Milestones only advance for events that can actually be measured - opening a link alone never earns a reward.
            </p>
          </Card>
        </section>
      )}

      {/* Stats */}
      {stats && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Referral progress</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              ["Link visits", stats.link_visits_measured, "where measurable"],
              ["Registrations", stats.registrations, ""],
              ["Contact verified", stats.contact_verified, ""],
              ["Pending / review", stats.pending + stats.under_review, ""],
              ["Approved", stats.approved, ""],
              ["Rejected", stats.rejected, ""],
            ].map(([label, value, hint]) => (
              <Card key={label as string} className="p-4 text-center">
                <p className="text-2xl font-bold text-stone-900">{value as number}</p>
                <p className="text-xs font-medium text-stone-600">{label as string}</p>
                {hint && <p className="text-[10px] text-stone-400">{hint as string}</p>}
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Campaigns */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Active campaigns</h2>
        {campaigns.length === 0 ? (
          <EmptyState title="No active referral campaigns" body="Administrators publish campaigns here with full terms." />
        ) : (
          <div className="space-y-3">
            {campaigns.map((c) => (
              <Card key={c.id} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">{c.name}</p>
                  <div className="flex gap-2">
                    <Badge tone="blue">reward: {c.reward_type}</Badge>
                    <StatusPill status={c.status} />
                  </div>
                </div>
                <p className="mt-1 text-sm text-stone-600">{c.description}</p>
                <div className="mt-2 space-y-1 text-xs text-stone-500">
                  <p><strong>Eligible event:</strong> {c.eligible_event.replace(/_/g, " ")}</p>
                  <p><strong>Eligibility rules:</strong> {c.eligibility_rules}</p>
                  <p><strong>Terms:</strong> {c.terms}</p>
                  {c.end_at && <p><strong>Ends:</strong> {new Date(c.end_at).toLocaleDateString()}</p>}
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* History */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Referral activity history</h2>
        {(history?.referrals ?? []).length === 0 ? (
          <EmptyState
            title="No referrals yet"
            body="Share your invite link. Statuses only appear for events that can actually be measured - opening a link alone never earns a reward."
          />
        ) : (
          <Card className="divide-y divide-stone-100">
            {history?.referrals.map((r) => (
              <div key={r.id} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">
                    <Users size={14} className="mr-1 inline text-stone-400" />
                    {r.referred_name ?? "Anonymous visitor"}
                    <span className="ml-2 text-xs text-stone-400">via {r.source.replace(/_/g, " ")}</span>
                  </p>
                  <div className="flex items-center gap-2">
                    {r.reward && <Badge tone={r.reward.status === "issued" ? "green" : "blue"}>{r.reward.type} · {r.reward.status}</Badge>}
                    <StatusPill status={r.status} />
                  </div>
                </div>
                {r.flag_reasons.length > 0 && (
                  <p className="mt-1 text-xs text-amber-700">Under review: {r.flag_reasons.join(", ")}</p>
                )}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {r.events.map((e, i) => (
                    <span key={i} className="rounded-full bg-stone-100 px-2 py-0.5 text-[11px] text-stone-600">
                      {e.type.replace(/_/g, " ")} · {new Date(e.at).toLocaleDateString()}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </Card>
        )}
        {(history?.pre_registration_events ?? []).length > 0 && (
          <p className="mt-2 text-xs text-stone-500">
            Plus {history?.pre_registration_events.length} pre-registration link event(s) recorded.
          </p>
        )}
      </section>

      <Notice kind="info">
        Referral rewards are non-cash recognition (badges, certificates, education). They are
        never paid for blood donations, donor matches or request fulfilment. Suspected abuse is
        reviewed by administrators - accounts are not auto-banned.
      </Notice>
    </div>
  );
}
