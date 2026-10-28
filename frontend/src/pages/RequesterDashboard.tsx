import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { Button, Card, EmptyState, ErrorText, Notice, PageHeader, Spinner, StatusPill } from "../components/ui";
import type { BloodRequest, Notification } from "../types";

export default function RequesterDashboard() {
  const { user } = useAuth();
  const [requests, setRequests] = useState<BloodRequest[] | null>(null);
  const [activity, setActivity] = useState<Notification[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api<{ requests: BloodRequest[] }>("/api/requests");
      setRequests(data.requests);
      const n = await api<{ notifications: Notification[] }>("/api/notifications");
      setActivity(n.notifications.slice(0, 8));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const active = (requests ?? []).filter((r) => !["fulfilled", "cancelled", "expired"].includes(r.status));
  const past = (requests ?? []).filter((r) => ["fulfilled", "cancelled", "expired"].includes(r.status));

  return (
    <div className="space-y-8">
      <PageHeader
        title={`Hello, ${user?.name?.split(" ")[0]}`}
        subtitle="Track your blood requests and their progress."
        actions={<Link to="/requests/new"><Button>New blood request</Button></Link>}
      />
      {error && <ErrorText>{error}</ErrorText>}

      <section>
        <h2 className="mb-3 text-lg font-semibold">Active requests</h2>
        {requests === null ? (
          <Spinner />
        ) : active.length === 0 ? (
          <EmptyState
            title="No active requests"
            body="When someone needs blood, create a request and BloodBridge will look for potentially compatible donors nearby."
            action={<Link to="/requests/new"><Button size="sm">Create a request</Button></Link>}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {active.map((r) => (
              <Card key={r.public_id} className="p-5">
                <div className="flex items-center justify-between">
                  <span className="rounded-lg bg-brand-600 px-2.5 py-1 text-sm font-bold text-white">{r.blood_group}</span>
                  <StatusPill status={r.status} />
                </div>
                <p className="mt-3 text-sm font-medium">{r.hospital}</p>
                <p className="text-sm text-stone-500">{r.locality ? `${r.locality}, ` : ""}{r.city} · {r.units} unit(s) · {r.urgency}</p>
                <p className="mt-1 text-xs text-stone-500">Needed by {new Date(r.needed_by).toLocaleString()}</p>
                <div className="mt-3 flex gap-2">
                  <Link to={`/requests/${r.public_id}/matches`}><Button size="sm" variant="secondary">View matches</Button></Link>
                  <Link to={`/requests/${r.public_id}`}><Button size="sm" variant="ghost">Tracking</Button></Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Request history</h2>
        {past.length === 0 ? (
          <p className="text-sm text-stone-500">No closed requests yet.</p>
        ) : (
          <Card className="divide-y divide-stone-100">
            {past.map((r) => (
              <div key={r.public_id} className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
                <div>
                  <span className="font-medium">{r.public_id}</span> · {r.blood_group} · {r.hospital}
                  {r.closed_reason && <p className="text-xs text-stone-500">{r.closed_reason}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill status={r.status} />
                  <Link to={`/requests/${r.public_id}`} className="text-brand-700 hover:underline">View</Link>
                </div>
              </div>
            ))}
          </Card>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Recent activity</h2>
        {activity.length === 0 ? (
          <p className="text-sm text-stone-500">No notifications yet.</p>
        ) : (
          <Card className="divide-y divide-stone-100">
            {activity.map((n) => (
              <div key={n.id} className="p-4 text-sm">
                <p className="font-medium">{n.title}</p>
                {n.body && <p className="text-xs text-stone-500">{n.body}</p>}
              </div>
            ))}
          </Card>
        )}
      </section>

      <Notice kind="info">
        Matching supports preliminary donor discovery only. Compatibility and donor eligibility
        must be assessed by qualified healthcare professionals, including testing and crossmatching.
      </Notice>
    </div>
  );
}
