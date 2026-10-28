import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Bell, Droplet, HeartHandshake, LayoutDashboard, LogOut, MessageSquareHeart,
  Settings2, Shield, Gift, Users,
} from "lucide-react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import type { Notification } from "../types";
import { Button } from "./ui";

const SAFETY_NOTICE =
  "BloodBridge supports preliminary donor discovery only. It does not provide medical advice, does not guarantee donors or blood availability, and never replaces professional transfusion services. In an emergency, contact your hospital or blood bank immediately.";

export default function Layout() {
  const { user, logout, loading } = useAuth();
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<Notification[] | null>(null);
  const [unread, setUnread] = useState(0);
  const [bellOpen, setBellOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) {
      setNotifications(null);
      return;
    }
    api<{ notifications: Notification[]; unread_count: number }>("/api/notifications")
      .then((r) => {
        setNotifications(r.notifications);
        setUnread(r.unread_count);
      })
      .catch(() => setNotifications([]));
  }, [user]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) setBellOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const markRead = async () => {
    try {
      await api("/api/notifications/read-all", { method: "POST" });
      setUnread(0);
      setNotifications((prev) => prev?.map((n) => ({ ...n, read: true })) ?? null);
    } catch {
      /* non-critical */
    }
  };

  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-brand-50 text-brand-700" : "text-stone-600 hover:bg-stone-100"}`;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-stone-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4">
          <Link to="/" className="flex items-center gap-2 font-semibold text-stone-900">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Droplet size={18} />
            </span>
            BloodBridge
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            <NavLink to="/requests/new" className={linkCls}>Find Blood</NavLink>
            <NavLink to="/donors/register" className={linkCls}>Become a Donor</NavLink>
            <NavLink to="/assistant" className={linkCls}>Bridge Assistant</NavLink>
            {user && <NavLink to="/rewards" className={linkCls}>Rewards</NavLink>}
            {user && <NavLink to="/referrals" className={linkCls}>Referrals</NavLink>}
            {user?.role === "donor" && (
              <NavLink to="/dashboard/donor" className={linkCls}>Donor Hub</NavLink>
            )}
            {user && user.role !== "admin" && user.role !== "donor" && (
              <NavLink to="/dashboard/requester" className={linkCls}>My Requests</NavLink>
            )}
            {user?.role === "admin" && (
              <NavLink to="/admin" className={linkCls}><span className="inline-flex items-center gap-1.5"><Shield size={15} /> Admin</span></NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {loading ? null : user ? (
              <>
                <div className="relative" ref={bellRef}>
                  <button
                    className="relative rounded-lg p-2 text-stone-500 hover:bg-stone-100"
                    onClick={() => setBellOpen((o) => !o)}
                    aria-label="Notifications"
                  >
                    <Bell size={18} />
                    {unread > 0 && (
                      <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-600 px-1 text-[10px] font-semibold text-white">
                        {unread}
                      </span>
                    )}
                  </button>
                  {bellOpen && (
                    <div className="absolute right-0 mt-2 w-80 rounded-xl border border-stone-200 bg-white p-2 shadow-lg">
                      <div className="flex items-center justify-between px-2 py-1">
                        <span className="text-sm font-semibold">Activity</span>
                        {unread > 0 && (
                          <button className="text-xs text-brand-700 hover:underline" onClick={markRead}>
                            Mark all read
                          </button>
                        )}
                      </div>
                      <div className="max-h-80 overflow-auto">
                        {(notifications ?? []).length === 0 && (
                          <p className="p-3 text-sm text-stone-500">No activity yet.</p>
                        )}
                        {(notifications ?? []).map((n) => (
                          <div key={n.id} className={`rounded-lg p-2 text-sm ${n.read ? "" : "bg-brand-50/60"}`}>
                            <p className="font-medium text-stone-800">{n.title}</p>
                            {n.body && <p className="text-xs text-stone-500">{n.body}</p>}
                            {n.link && (
                              <Link to={n.link} className="text-xs text-brand-700 hover:underline" onClick={() => setBellOpen(false)}>
                                View
                              </Link>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <span className="hidden text-sm text-stone-600 sm:block">{user.name}</span>
                <Button variant="ghost" size="sm" onClick={() => { logout(); navigate("/"); }}>
                  <LogOut size={15} /> Log out
                </Button>
              </>
            ) : (
              <Link to="/login">
                <Button variant="secondary" size="sm">Log in</Button>
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-stone-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-6">
          <p className="flex items-start gap-2 text-xs text-stone-500">
            <HeartHandshake size={14} className="mt-0.5 shrink-0" />
            {SAFETY_NOTICE}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-stone-500">
            <span className="inline-flex items-center gap-1"><Droplet size={12} /> BloodBridge - community demo build</span>
            <Link to="/rewards" className="inline-flex items-center gap-1 hover:text-stone-800"><Gift size={12} /> Community rewards</Link>
            <Link to="/referrals" className="inline-flex items-center gap-1 hover:text-stone-800"><Users size={12} /> Community invites</Link>
            <Link to="/assistant" className="inline-flex items-center gap-1 hover:text-stone-800"><MessageSquareHeart size={12} /> Bridge Assistant</Link>
            <span className="inline-flex items-center gap-1"><Settings2 size={12} /> Recognition is never tied to donation</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
