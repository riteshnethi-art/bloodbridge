import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { Button, Card, ErrorText, Field, Notice, PageHeader } from "../components/ui";
import { BLOOD_GROUPS } from "../utils/validate";

const CONTACT_PREFS = [
  { value: "in_app", label: "In-app only (most private)" },
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone" },
  { value: "whatsapp", label: "WhatsApp" },
];

export default function DonorRegister() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const ref = (params.get("ref") ?? "").trim().toUpperCase();

  const [form, setForm] = useState({
    name: "", email: "", password: "", phone: "",
    blood_group: "", city: "", locality: "", lat: "", lng: "",
    preferred_contact: "in_app", availability: "available",
    discoverable: true, allow_direct_contact: false, can_receive_urgent: true,
    privacyAccepted: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [geoState, setGeoState] = useState<"idle" | "granted" | "denied">("idle");

  useEffect(() => {
    if (user) setForm((f) => ({ ...f, name: f.name || user.name, email: f.email || user.email }));
  }, [user]);

  const set = (key: string, value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));

  const useMyLocation = () => {
    // Browser geolocation only after explicit permission; manual entry stays available.
    if (!navigator.geolocation) {
      setGeoState("denied");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoState("granted");
        set("lat", pos.coords.latitude.toFixed(4));
        set("lng", pos.coords.longitude.toFixed(4));
      },
      () => setGeoState("denied"),
      { timeout: 8000 },
    );
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const errs: Record<string, string> = {};
    if (form.name.trim().length < 2) errs.name = "Name is required";
    if (!/^\S+@\S+\.\S+$/.test(form.email)) errs.email = "A valid email is required";
    if (!user && form.password.length < 8) errs.password = "Password must be at least 8 characters";
    if (!BLOOD_GROUPS.includes(form.blood_group as (typeof BLOOD_GROUPS)[number])) errs.blood_group = "Select your blood group";
    if (form.city.trim().length < 2) errs.city = "City is required";
    if (!form.privacyAccepted) errs.privacyAccepted = "The privacy notice must be accepted";
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setBusy(true);
    try {
      const account = user ?? (await register({
        name: form.name, email: form.email, password: form.password,
        phone: form.phone || undefined, role: "donor",
        privacy_accepted: true, referral_code: ref || undefined,
      }));
      await api("/api/donors", {
        body: {
          blood_group: form.blood_group,
          city: form.city.trim(),
          locality: form.locality.trim(),
          lat: form.lat ? Number(form.lat) : null,
          lng: form.lng ? Number(form.lng) : null,
          preferred_contact: form.preferred_contact,
          availability: form.availability,
          discoverable: form.discoverable,
          allow_direct_contact: form.allow_direct_contact,
          can_receive_urgent: form.can_receive_urgent,
        },
      });
      navigate("/dashboard/donor");
      void account;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Become a donor"
        subtitle="Register your donor profile. You control discoverability, availability and how you are contacted."
      />

      <Notice kind="info">
        Registration does not guarantee eligibility to donate at any particular time. Actual
        eligibility is determined by qualified blood-donation professionals at the donation site.
      </Notice>

      <Card className="mt-4 p-6">
        <form onSubmit={submit} className="space-y-5">
          {!user && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name" error={errors.name}>
                <input className="input-base" value={form.name} onChange={(e) => set("name", e.target.value)} required />
              </Field>
              <Field label="Email" error={errors.email}>
                <input className="input-base" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required />
              </Field>
              <Field label="Password" error={errors.password} hint="At least 8 characters.">
                <input className="input-base" type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required />
              </Field>
              <Field label="Phone (optional)">
                <input className="input-base" value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="+91..." />
              </Field>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Blood group" error={errors.blood_group}>
              <select className="input-base" value={form.blood_group} onChange={(e) => set("blood_group", e.target.value)} required>
                <option value="">Select...</option>
                {BLOOD_GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </Field>
            <Field label="Availability">
              <select className="input-base" value={form.availability} onChange={(e) => set("availability", e.target.value)}>
                <option value="available">Available</option>
                <option value="maybe">Maybe / call to confirm</option>
                <option value="unavailable">Unavailable</option>
              </select>
            </Field>
            <Field label="City" error={errors.city}>
              <input className="input-base" value={form.city} onChange={(e) => set("city", e.target.value)} placeholder="Hyderabad" required />
            </Field>
            <Field label="Locality / area" hint="General area only - never your full address.">
              <input className="input-base" value={form.locality} onChange={(e) => set("locality", e.target.value)} placeholder="Gachibowli" />
            </Field>
          </div>

          <div className="rounded-lg border border-stone-200 p-4">
            <p className="text-sm font-medium text-stone-700">Location precision (optional)</p>
            <p className="mt-1 text-xs text-stone-500">
              Coordinates improve approximate distance estimates. They are never shown to
              requesters - only "≈ X km" is displayed. Manual entry works too.
            </p>
            <div className="mt-2 flex flex-wrap items-end gap-2">
              <input className="input-base w-32" value={form.lat} onChange={(e) => set("lat", e.target.value)} placeholder="Latitude" />
              <input className="input-base w-32" value={form.lng} onChange={(e) => set("lng", e.target.value)} placeholder="Longitude" />
              <Button type="button" variant="secondary" size="sm" onClick={useMyLocation}>Use my location</Button>
            </div>
            {geoState === "denied" && <p className="mt-1 text-xs text-amber-700">Location permission denied or unavailable - you can type coordinates or leave them empty.</p>}
          </div>

          <Field label="Preferred contact method">
            <select className="input-base" value={form.preferred_contact} onChange={(e) => set("preferred_contact", e.target.value)}>
              {CONTACT_PREFS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </Field>

          <div className="space-y-2.5 rounded-lg border border-stone-200 p-4">
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5" checked={form.discoverable} onChange={(e) => set("discoverable", e.target.checked)} />
              <span><strong>Discoverable.</strong> Allow my blood group, general area and availability to appear in match results.</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5" checked={form.allow_direct_contact} onChange={(e) => set("allow_direct_contact", e.target.checked)} />
              <span><strong>Contact consent.</strong> After I accept a contact request, share my phone/email with that requester. If unchecked, coordination stays in-app.</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5" checked={form.can_receive_urgent} onChange={(e) => set("can_receive_urgent", e.target.checked)} />
              <span><strong>Urgent requests.</strong> I am open to being contacted for critical and urgent needs.</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5" checked={form.privacyAccepted ?? false} onChange={(e) => set("privacyAccepted", e.target.checked)} />
              <span><strong>Privacy notice.</strong> I understand BloodBridge stores my profile to enable matching, never publicly exposes my phone number, exact address or precise coordinates, and that I can pause or delete my profile anytime. *</span>
            </label>
            {errors.privacyAccepted && <p className="text-xs text-brand-700">{errors.privacyAccepted}</p>}
          </div>

          {error && <ErrorText>{error}</ErrorText>}
          <Button type="submit" loading={busy} className="w-full">
            {user ? "Create donor profile" : "Register as a donor"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
