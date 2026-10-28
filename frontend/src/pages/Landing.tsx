import { Link } from "react-router-dom";
import {
  ArrowRight, Droplet, Handshake, MapPin, MessageSquareHeart, Search,
  ShieldCheck, Gift, Users, Clock, AlertTriangle,
} from "lucide-react";
import { Card } from "../components/ui";

const STEPS = [
  { icon: Search, title: "1. Submit a request", body: "Tell us the blood group, location, hospital, units, urgency and needed-by time - by form or through a chat with Bridge Assistant." },
  { icon: MapPin, title: "2. Discover potential donors", body: "We filter registered donors by blood compatibility, availability and consent, then rank candidates by proximity and availability freshness." },
  { icon: Handshake, title: "3. Initiate permitted contact", body: "You send a contact request through BloodBridge. Donors decide whether to respond - contact details stay private until a donor accepts." },
  { icon: Clock, title: "4. Track and close", body: "Follow your request from matching to fulfilment or cancellation. BloodBridge never marks a request fulfilled just because a donor was found." },
];

export default function Landing() {
  return (
    <div className="space-y-16">
      {/* Hero */}
      <section className="grid items-center gap-8 md:grid-cols-2">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
            <Droplet size={13} /> Community blood donor discovery
          </span>
          <h1 className="mt-4 text-4xl font-bold tracking-tight text-stone-900 md:text-5xl">
            Help reaches faster when <span className="text-brand-600">the community is connected.</span>
          </h1>
          <p className="mt-4 max-w-lg text-stone-600">
            BloodBridge helps people discover potentially compatible blood donors based on
            blood group, location, availability and urgency - with conversational request
            intake, transparent matching, community rewards and referrals.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/requests/new" className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-brand-700">
              Find Blood <ArrowRight size={16} />
            </Link>
            <Link to="/donors/register" className="inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-5 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-100">
              Become a Donor
            </Link>
            <Link to="/assistant" className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium text-brand-700 hover:bg-brand-50">
              <MessageSquareHeart size={16} /> Try Bridge Assistant
            </Link>
          </div>
        </div>
        <Card className="p-6">
          <div className="rounded-lg bg-stone-50 p-4">
            <p className="text-sm font-medium text-stone-700">Compatibility at a glance</p>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-stone-600">
              {[
                ["O-", "O-"], ["O+", "O-, O+"], ["A-", "O-, A-"], ["A+", "O-, O+, A-, A+"],
                ["B-", "O-, B-"], ["B+", "O-, O+, B-, B+"], ["AB-", "O-, A-, B-, AB-"], ["AB+", "All eight groups"],
              ].map(([r, d]) => (
                <div key={r} className="rounded-md border border-stone-200 bg-white p-2">
                  <span className="font-semibold text-brand-700">{r}</span> recipient
                  <div className="mt-0.5 text-stone-500">← {d}</div>
                </div>
              ))}
            </div>
          </div>
          <p className="mt-3 text-xs text-stone-500">
            These results support preliminary donor discovery only. Blood transfusion
            compatibility and donor eligibility must be assessed by qualified healthcare
            professionals, including appropriate testing and crossmatching.
          </p>
        </Card>
      </section>

      {/* Problem statement */}
      <section>
        <h2 className="text-2xl font-semibold tracking-tight">Why BloodBridge exists</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {[
            { t: "Finding donors is slow", b: "In urgent moments, families forward messages hoping someone nearby, compatible and available will respond." },
            { t: "Information is scattered", b: "Availability, location and willingness live in people's heads and group chats - not in one place that can be searched safely." },
            { t: "Privacy is often ignored", b: "Public forwarding exposes phone numbers and addresses. BloodBridge mediates contact and protects donor identity by design." },
          ].map((c) => (
            <Card key={c.t} className="p-5">
              <h3 className="font-semibold text-stone-800">{c.t}</h3>
              <p className="mt-1.5 text-sm text-stone-600">{c.b}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section>
        <h2 className="text-2xl font-semibold tracking-tight">How it works</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-4">
          {STEPS.map((s) => (
            <Card key={s.title} className="p-5">
              <s.icon size={20} className="text-brand-600" />
              <h3 className="mt-2 font-semibold text-stone-800">{s.title}</h3>
              <p className="mt-1.5 text-sm text-stone-600">{s.body}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* Community participation */}
      <section className="grid gap-4 md:grid-cols-2">
        <Card className="p-6">
          <span className="inline-flex items-center gap-2 text-brand-700"><Gift size={18} /> Community rewards</span>
          <h3 className="mt-2 text-lg font-semibold">Recognition for participation - never payment for donation</h3>
          <p className="mt-2 text-sm text-stone-600">
            Earn badges, participation certificates and approved non-cash partner offers for
            completing verification, education modules and community events. Rewards are never
            given for donating blood, and never include cash.
          </p>
          <Link to="/rewards" className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
            Explore rewards <ArrowRight size={14} />
          </Link>
        </Card>
        <Card className="p-6">
          <span className="inline-flex items-center gap-2 text-brand-700"><Users size={18} /> Community invites</span>
          <h3 className="mt-2 text-lg font-semibold">Grow the community with your own invite link</h3>
          <p className="mt-2 text-sm text-stone-600">
            Every member gets a unique referral link. When someone you invited joins and
            completes community onboarding, you can earn non-cash recognition - subject to
            campaign rules and review. Referrals are never paid for blood donations.
          </p>
          <Link to="/referrals" className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
            See the referral program <ArrowRight size={14} />
          </Link>
        </Card>
      </section>

      {/* Safety notice */}
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
        <p className="flex items-start gap-2 text-sm text-amber-900">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <span>
            <strong>Safety notice.</strong> Registration and matching do not guarantee
            eligibility to donate or receive blood. Actual eligibility and transfusion
            compatibility are determined by qualified blood-donation professionals, including
            appropriate testing and crossmatching. BloodBridge does not promise to find blood.
            For emergencies, contact your hospital or a regional blood centre immediately.
          </span>
        </p>
      </section>
    </div>
  );
}
