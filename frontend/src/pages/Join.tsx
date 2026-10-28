import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { Button, Card, ErrorText, Field, Notice, PageHeader } from "../components/ui";
import { isEmail, isPhone } from "../utils/validate";

export default function Join() {
  const [params] = useSearchParams();
  const ref = (params.get("ref") ?? "").trim().toUpperCase();
  const { register, user } = useAuth();
  const navigate = useNavigate();

  const [tracked, setTracked] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", phone: "", role: "requester" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (ref && !tracked) {
      setTracked(true);
      // link_opened is measured only when someone actually opens this page.
      api("/api/referrals/track", { body: { code: ref, event_type: "link_opened", reference: `page-${Date.now()}` } })
        .catch(() => undefined);
      api("/api/referrals/track", { body: { code: ref, event_type: "registration_started", reference: `page-${Date.now()}` } })
        .catch(() => undefined);
    }
  }, [ref, tracked]);

  useEffect(() => {
    if (user) setDone(true);
  }, [user]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!isEmail(form.email) && !isPhone(form.phone)) {
      setError("Provide a valid email (a phone number is optional but recommended).");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      await register({ ...form, privacy_accepted: true, referral_code: ref || undefined });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <PageHeader
        title="Join BloodBridge"
        subtitle="A community platform that helps people discover potential blood donors and access blood-request resources."
      />
      {ref && (
        <div className="mb-4">
          <Notice kind="success">
            You were invited with referral code <strong className="font-mono">{ref}</strong>. It will be
            credited to your inviter when you complete community onboarding.
          </Notice>
        </div>
      )}
      {done ? (
        <Card className="p-6 text-center">
          <p className="text-lg font-semibold">You're in - welcome to the community!</p>
          <p className="mt-2 text-sm text-stone-600">
            Next step: complete community onboarding to unlock rewards and finish your referral.
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <Button onClick={() => navigate("/onboarding")}>Complete onboarding</Button>
            <Button variant="secondary" onClick={() => navigate("/")}>Go to home</Button>
          </div>
        </Card>
      ) : (
        <Card className="p-6">
          <form onSubmit={submit} className="space-y-4">
            <Field label="Full name">
              <input className="input-base" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required minLength={2} />
            </Field>
            <Field label="Email">
              <input className="input-base" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            </Field>
            <Field label="Phone (optional)">
              <input className="input-base" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+91..." />
            </Field>
            <Field label="Password" hint="At least 8 characters.">
              <input className="input-base" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={8} />
            </Field>
            <Field label="I want to join as">
              <select className="input-base" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="requester">Community member (requester)</option>
                <option value="donor">Donor</option>
              </select>
            </Field>
            {error && <ErrorText>{error}</ErrorText>}
            <Button type="submit" loading={busy} className="w-full">Create account</Button>
            <p className="text-xs text-stone-500">
              By creating an account you accept the privacy notice. Demo mode: contact
              verification is simulated. Joining does not guarantee access to blood, donors
              or any medical service.
            </p>
          </form>
        </Card>
      )}
      <p className="mt-4 text-center text-sm text-stone-600">
        Already a member? <Link to="/login" className="font-medium text-brand-700 hover:underline">Log in</Link>
      </p>
    </div>
  );
}
