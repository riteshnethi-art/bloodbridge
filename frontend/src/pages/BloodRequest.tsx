import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { Button, Card, ErrorText, Field, Notice, PageHeader, StatusPill } from "../components/ui";
import { BLOOD_GROUPS, URGENCIES, validateRequestForm } from "../utils/validate";
import type { BloodRequest } from "../types";

const URGENCY_LABELS: Record<string, string> = {
  critical: "Critical - needed immediately",
  urgent: "Urgent - within 24-48 hours",
  routine: "Routine - planned transfusion",
};

export default function BloodRequest() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    blood_group: "", city: "", locality: "", hospital: "",
    units: "1", urgency: "urgent", needed_by: "",
    requester_name: user?.name ?? "", contact_value: user?.phone ?? user?.email ?? "",
    contact_method: user?.phone ? "phone" : "email", notes: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [step, setStep] = useState<"form" | "confirm" | "done">("form");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<BloodRequest | null>(null);
  const [matchesFound, setMatchesFound] = useState(0);

  const set = (key: string, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const next = () => {
    const errs = validateRequestForm(form);
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;
    setStep("confirm");
  };

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const out = await api<{ request: BloodRequest; matches_found: number }>("/api/requests", {
        body: {
          ...form,
          units: Number(form.units),
          needed_by: new Date(form.needed_by).toISOString(),
        },
      });
      setCreated(out.request);
      setMatchesFound(out.matches_found);
      setStep("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
      setStep("form");
    } finally {
      setBusy(false);
    }
  };

  if (step === "done" && created) {
    return (
      <div className="mx-auto max-w-xl">
        <PageHeader title={`Request ${created.public_id} submitted`} subtitle="Your request is now visible to the matching engine." />
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <StatusPill status={created.status} />
            <span className="text-sm text-stone-500">{matchesFound} potential donor(s) found</span>
          </div>
          <div className="mt-4 space-y-1 text-sm text-stone-700">
            <p><strong>Blood group:</strong> {created.blood_group}</p>
            <p><strong>Location:</strong> {created.locality ? `${created.locality}, ` : ""}{created.city}</p>
            <p><strong>Hospital:</strong> {created.hospital}</p>
            <p><strong>Units:</strong> {created.units} · <strong>Urgency:</strong> {created.urgency}</p>
            <p><strong>Needed by:</strong> {new Date(created.needed_by).toLocaleString()}</p>
          </div>
          <div className="mt-5 flex gap-2">
            <Button onClick={() => navigate(`/requests/${created.public_id}/matches`)}>
              View potential donors <ArrowRight size={16} />
            </Button>
            <Button variant="secondary" onClick={() => navigate("/dashboard/requester")}>
              My requests
            </Button>
          </div>
        </Card>
        <div className="mt-4 space-y-3">
          <Notice kind="warning">
            BloodBridge does not guarantee that donors or blood will be found. For emergencies,
            contact your hospital or blood bank immediately.
          </Notice>
          <Notice kind="info">{created.compatibility_notice}</Notice>
        </div>
      </div>
    );
  }

  if (step === "confirm") {
    return (
      <div className="mx-auto max-w-xl">
        <PageHeader title="Confirm your request" subtitle="Please review the details before submitting." />
        <Card className="p-6">
          <dl className="space-y-2 text-sm">
            {[
              ["Blood group", form.blood_group],
              ["Location", [form.locality, form.city].filter(Boolean).join(", ")],
              ["Hospital / collection location", form.hospital],
              ["Units required", form.units],
              ["Urgency", URGENCY_LABELS[form.urgency]],
              ["Needed by", new Date(form.needed_by).toLocaleString()],
              ["Coordinator", form.requester_name],
              ["Contact", `${form.contact_value} (${form.contact_method})`],
              ["Additional information", form.notes || "-"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 border-b border-stone-100 pb-2">
                <dt className="text-stone-500">{k}</dt>
                <dd className="text-right font-medium text-stone-800">{v}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-5 flex gap-2">
            <Button onClick={submit} loading={busy}>Confirm & submit</Button>
            <Button variant="secondary" onClick={() => setStep("form")}>Edit details</Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Create a blood request"
        subtitle="Tell us what is needed. We will look for potentially compatible, available donors nearby."
      />
      <Card className="p-6">
        <form onSubmit={(e) => { e.preventDefault(); next(); }} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Required blood group" error={errors.blood_group}>
              <select className="input-base" value={form.blood_group} onChange={(e) => set("blood_group", e.target.value)} required>
                <option value="">Select...</option>
                {BLOOD_GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </Field>
            <Field label="Units required" error={errors.units}>
              <input className="input-base" type="number" min={1} max={20} value={form.units} onChange={(e) => set("units", e.target.value)} required />
            </Field>
            <Field label="City" error={errors.city}>
              <input className="input-base" value={form.city} onChange={(e) => set("city", e.target.value)} placeholder="Hyderabad" required />
            </Field>
            <Field label="Locality / area">
              <input className="input-base" value={form.locality} onChange={(e) => set("locality", e.target.value)} placeholder="Gachibowli" />
            </Field>
          </div>

          <Field label="Hospital or collection location" error={errors.hospital}>
            <input className="input-base" value={form.hospital} onChange={(e) => set("hospital", e.target.value)} placeholder="Demo Multispeciality Hospital" required />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Urgency" error={errors.urgency}>
              <select className="input-base" value={form.urgency} onChange={(e) => set("urgency", e.target.value)}>
                {URGENCIES.map((u) => <option key={u} value={u}>{URGENCY_LABELS[u]}</option>)}
              </select>
            </Field>
            <Field label="Needed by" error={errors.needed_by}>
              <input className="input-base" type="datetime-local" value={form.needed_by} onChange={(e) => set("needed_by", e.target.value)} required />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Coordinator name" error={errors.requester_name}>
              <input className="input-base" value={form.requester_name} onChange={(e) => set("requester_name", e.target.value)} required />
            </Field>
            <Field label="Contact phone or email" error={errors.contact_value} hint="Shared with a donor only after they accept contact.">
              <input className="input-base" value={form.contact_value} onChange={(e) => set("contact_value", e.target.value)} required />
            </Field>
          </div>

          <Field label="Preferred contact method">
            <select className="input-base" value={form.contact_method} onChange={(e) => set("contact_method", e.target.value)}>
              <option value="phone">Phone</option>
              <option value="email">Email</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </Field>

          <Field label="Additional information (optional)">
            <textarea className="input-base min-h-20" value={form.notes} onChange={(e) => set("notes", e.target.value)} />
          </Field>

          {error && <ErrorText>{error}</ErrorText>}
          <Button type="submit">Review request</Button>
        </form>
      </Card>
      <div className="mt-4">
        <Notice kind="info">
          After submission you will see candidate donors with matching criteria explained. A
          found donor is never a guarantee - compatibility and eligibility are confirmed by
          healthcare professionals.
        </Notice>
      </div>
    </div>
  );
}
