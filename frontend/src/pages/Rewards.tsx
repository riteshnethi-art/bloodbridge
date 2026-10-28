import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Award, BookOpenCheck, Check, CheckCircle2, Circle, Copy, Gift, BadgeCheck, Users,
} from "lucide-react";
import { api } from "../api";
import {
  Badge, Button, Card, EmptyState, ErrorText, Notice, PageHeader, Spinner,
} from "../components/ui";
import type { Recognition, RewardOffer, Wallet } from "../types";

function copy(text: string): Promise<void> {
  if (navigator.clipboard) return navigator.clipboard.writeText(text);
  return Promise.resolve();
}

export default function Rewards() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [offers, setOffers] = useState<RewardOffer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [copied, setCopied] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [w, o] = await Promise.all([
        api<Wallet>("/api/rewards/wallet"),
        api<{ offers: RewardOffer[] }>("/api/rewards/offers"),
      ]);
      setWallet(w);
      setOffers(o.offers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load rewards");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const claim = async (id: number) => {
    setMessage("");
    setError("");
    try {
      const out = await api<{ claim_code: string }>(`/api/rewards/offers/${id}/claim`, { body: {} });
      setMessage(`Offer claimed! Your secure claim reference is ${out.claim_code}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Claim failed");
    }
  };

  const completeModule = async (key: string) => {
    setMessage("");
    setError("");
    try {
      await api("/api/rewards/education/complete", { body: { module_key: key } });
      setMessage("Education module completed - recognition added to your wallet.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not complete module");
    }
  };

  if (loading) return <Spinner label="Loading your rewards wallet..." />;

  const recognition: Recognition[] = [
    ...(wallet?.badges ?? []),
    ...(wallet?.certificates ?? []),
    ...(wallet?.education ?? []),
  ];
  const has = (source: string) => recognition.some((r) => r.source === source);

  // Onboarding funnel: turn the wallet into an actionable "first wins" checklist.
  const steps = [
    {
      title: "Welcome badge",
      desc: "Yours automatically for joining BloodBridge - it is already in your wallet.",
      done: has("onboarding"),
      cta: null as { label: string; to: string } | null,
    },
    {
      title: "Learn the basics",
      desc: "Complete any education module below - takes two minutes, earns a learning badge.",
      done: (wallet?.education.length ?? 0) > 0,
      cta: { label: "Pick a module", to: "#education-modules" },
    },
    {
      title: "Get a Verified Donor Profile",
      desc: "Complete your donor profile. Once an admin verifies it, you earn the verification badge.",
      done: has("profile_verification"),
      cta: { label: "Complete profile", to: "/donors/register" },
    },
    {
      title: "Invite a friend",
      desc: "When someone you invited joins and completes onboarding, you earn the Community Connector badge.",
      done: has("referral_campaign"),
      cta: { label: "Get my invite link", to: "/referrals" },
    },
  ];
  const openSteps = steps.filter((s) => !s.done);
  const modulesDone = wallet?.education.length ?? 0;
  const modulesTotal = wallet?.education_modules_available.length ?? 0;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Community rewards"
        subtitle="Badges, certificates and partner perks for being an active community member - plus recognition for inviting friends. Never cash, never tied to donation."
      />

      {message && <Notice kind="success">{message}</Notice>}
      {error && <ErrorText>{error}</ErrorText>}

      {/* Why this matters - the value, up front */}
      <section className="grid gap-4 md:grid-cols-3">
        <Card className="p-5">
          <Gift size={22} className="text-brand-600" />
          <p className="mt-2 font-semibold">Real perks, zero cost</p>
          <p className="mt-1 text-sm text-stone-600">
            Claim offers from local partners - health checks, coffee and more. Free for
            active members; claim codes are yours to use.
          </p>
        </Card>
        <Card className="p-5">
          <BadgeCheck size={22} className="text-brand-600" />
          <p className="mt-2 font-semibold">Recognition you can show</p>
          <p className="mt-1 text-sm text-stone-600">
            Badges and certificates for learning and community participation - they build
            trust when you respond to requests.
          </p>
        </Card>
        <Card className="p-5">
          <Users size={22} className="text-brand-600" />
          <p className="mt-2 font-semibold">Invite friends, earn together</p>
          <p className="mt-1 text-sm text-stone-600">
            Every friend who joins through your invite and completes onboarding earns you
            the Community Connector badge.
          </p>
          <Link to="/referrals" className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
            Go to invites <span aria-hidden>&rarr;</span>
          </Link>
        </Card>
      </section>

      {/* First wins checklist - shown until everything is done */}
      {openSteps.length > 0 && (
        <section>
          <h2 className="mb-1 text-lg font-semibold">Get started - your first wins</h2>
          <p className="mb-3 text-sm text-stone-500">
            {4 - openSteps.length} of 4 done. Each one earns you a badge.
          </p>
          <Card className="divide-y divide-stone-100">
            {steps.map((s) => (
              <div key={s.title} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="flex items-start gap-3">
                  {s.done
                    ? <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-green-600" />
                    : <Circle size={20} className="mt-0.5 shrink-0 text-stone-300" />}
                  <div>
                    <p className={`text-sm font-medium ${s.done ? "text-stone-400 line-through" : "text-stone-900"}`}>
                      {s.title}
                    </p>
                    <p className="text-xs text-stone-500">{s.desc}</p>
                  </div>
                </div>
                {s.cta && !s.done && (
                  s.cta.to.startsWith("#")
                    ? <a href={s.cta.to} className="text-sm font-medium text-brand-700 hover:underline">{s.cta.label}</a>
                    : <Link to={s.cta.to} className="text-sm font-medium text-brand-700 hover:underline">{s.cta.label}</Link>
                )}
              </div>
            ))}
          </Card>
        </section>
      )}

      {/* Recognition */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Your recognition</h2>
        {recognition.length === 0 ? (
          <EmptyState
            title="No recognition yet"
            body="Work through the first-wins checklist above - the welcome badge may already be waiting after you finish onboarding."
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            {wallet?.badges.map((r) => (
              <Card key={r.id} className="p-5">
                <BadgeCheck size={22} className="text-brand-600" />
                <p className="mt-2 font-semibold">{r.title}</p>
                <p className="mt-1 text-xs text-stone-500">{r.description}</p>
                <p className="mt-2 font-mono text-xs text-stone-400">{r.reference}</p>
                <Badge tone="green">badge</Badge>
              </Card>
            ))}
            {wallet?.certificates.map((r) => (
              <Card key={r.id} className="p-5">
                <Award size={22} className="text-brand-600" />
                <p className="mt-2 font-semibold">{r.title}</p>
                <p className="mt-1 text-xs text-stone-500">{r.description}</p>
                <p className="mt-2 font-mono text-xs text-stone-400">{r.reference}</p>
                <Badge tone="blue">participation certificate</Badge>
              </Card>
            ))}
            {wallet?.education.map((r) => (
              <Card key={r.id} className="p-5">
                <BookOpenCheck size={22} className="text-brand-600" />
                <p className="mt-2 font-semibold">{r.title}</p>
                <p className="mt-1 text-xs text-stone-500">{r.description}</p>
                <p className="mt-2 font-mono text-xs text-stone-400">{r.reference}</p>
                <Badge tone="amber">education</Badge>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Education modules */}
      {wallet && wallet.education_modules_available.length > 0 && (
        <section id="education-modules">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">Education modules</h2>
            <p className="text-xs text-stone-500">{modulesDone} of {modulesTotal} completed</p>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {wallet.education_modules_available.map((m) => {
              const done = wallet.education.some((e) => e.title === m.title);
              return (
                <Card key={m.key} className="flex flex-col p-5">
                  <p className="font-semibold">{m.title}</p>
                  <p className="mt-1 flex-1 text-xs text-stone-500">{m.description}</p>
                  <Button size="sm" variant={done ? "ghost" : "secondary"} className="mt-3" disabled={done}
                          onClick={() => completeModule(m.key)}>
                    {done ? "Completed" : "Mark complete"}
                  </Button>
                </Card>
              );
            })}
          </div>
        </section>
      )}

      {/* Offers */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Partner offers</h2>
        {offers.length === 0 ? (
          <EmptyState title="No active offers" body="Check back later - administrators publish approved offers here." />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {offers.map((o) => {
              const myClaim = wallet?.claims.find((c) => c.offer.offer_ref === o.offer_ref);
              return (
                <Card key={o.id} className="flex flex-col p-5">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="inline-flex items-center gap-1.5 text-xs text-stone-500"><Gift size={12} /> {o.partner_name}</span>
                      <p className="mt-1 font-semibold">{o.title}</p>
                    </div>
                    <Badge tone={o.is_demo_partner ? "amber" : "green"}>{o.partner_label}</Badge>
                  </div>
                  <p className="mt-2 flex-1 text-sm text-stone-600">{o.description}</p>
                  <div className="mt-3 space-y-1 text-xs text-stone-500">
                    <p><strong>Eligibility:</strong> {o.eligibility_rules || "All community members"}</p>
                    <p><strong>Redemption:</strong> {o.redemption_instructions}</p>
                    <p>
                      <strong>Availability:</strong> {o.remaining} of {o.quantity} left
                      {o.valid_to ? ` · valid until ${new Date(o.valid_to).toLocaleDateString()}` : ""}
                      {(o.claim_count ?? 0) > 0 ? ` · ${o.claim_count} member${o.claim_count === 1 ? "" : "s"} claimed` : " · be the first to claim"}
                    </p>
                    <p><strong>Terms:</strong> {o.terms}</p>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button size="sm" disabled={Boolean(myClaim) || o.remaining <= 0}
                            onClick={() => claim(o.id)}>
                      {myClaim ? "Claimed" : o.remaining <= 0 ? "Sold out" : "Claim offer"}
                    </Button>
                    {myClaim && (
                      <button
                        className="inline-flex items-center gap-1 rounded border border-stone-300 px-2 py-1 font-mono text-xs hover:bg-stone-50"
                        onClick={() => { copy(myClaim.claim_code); setCopied(myClaim.claim_code); setTimeout(() => setCopied(null), 1500); }}
                      >
                        {copied === myClaim.claim_code ? <Check size={12} /> : <Copy size={12} />} {myClaim.claim_code}
                      </button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* Claim history */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Claim history</h2>
        {(wallet?.claims ?? []).length === 0 ? (
          <p className="text-sm text-stone-500">No claims yet.</p>
        ) : (
          <Card className="divide-y divide-stone-100">
            {wallet?.claims.map((c) => (
              <div key={c.claim_code} className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
                <div>
                  <p className="font-medium">{c.offer.title}</p>
                  <p className="text-xs text-stone-500">{c.offer.partner_name} · claimed {new Date(c.claimed_at).toLocaleDateString()}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    className="inline-flex items-center gap-1 rounded border border-stone-300 px-2 py-1 font-mono text-xs hover:bg-stone-50"
                    onClick={() => { copy(c.claim_code); setCopied(c.claim_code); setTimeout(() => setCopied(null), 1500); }}
                  >
                    {copied === c.claim_code ? <Check size={12} /> : <Copy size={12} />} {c.claim_code}
                  </button>
                  <Badge tone={c.status === "redeemed" ? "green" : c.status === "expired" ? "neutral" : "blue"}>{c.status}</Badge>
                </div>
              </div>
            ))}
          </Card>
        )}
      </section>

      <Notice kind="info">
        Rewards recognise community participation such as verification, education and events.
        BloodBridge never rewards donating blood, promising to donate, responding to requests or
        recruiting donors, and never offers cash. Real-world incentives require administrator
        approval and compliance review against voluntary donation guidelines.
      </Notice>
    </div>
  );
}
