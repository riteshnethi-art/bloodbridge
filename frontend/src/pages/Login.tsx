import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button, Card, ErrorText, Field, Notice, PageHeader } from "../components/ui";

const DEMO_ACCOUNTS = [
  { label: "Requester", email: "rahul@example.demo" },
  { label: "Donor", email: "aarav.donor@bloodbridge.demo" },
  { label: "Admin", email: "admin@bloodbridge.demo" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? "/dashboard/requester");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <PageHeader title="Log in" subtitle="Welcome back to BloodBridge." />
      <Card className="p-6">
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email">
            <input className="input-base" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Password">
            <input className="input-base" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {error && <ErrorText>{error}</ErrorText>}
          <Button type="submit" loading={busy} className="w-full">Log in</Button>
        </form>
      </Card>
      <div className="mt-4">
        <Notice kind="info">
          Demo accounts (password <code className="font-mono">demo123</code>):{" "}
          {DEMO_ACCOUNTS.map((a, i) => (
            <span key={a.email}>
              {i > 0 && ", "}
              <button type="button" className="font-medium underline" onClick={() => { setEmail(a.email); setPassword("demo123"); }}>
                {a.label}
              </button>
            </span>
          ))}
        </Notice>
      </div>
      <p className="mt-4 text-center text-sm text-stone-600">
        New here? <Link to="/donors/register" className="font-medium text-brand-700 hover:underline">Register as a donor</Link> or{" "}
        <Link to="/join" className="font-medium text-brand-700 hover:underline">join the community</Link>.
      </p>
    </div>
  );
}
