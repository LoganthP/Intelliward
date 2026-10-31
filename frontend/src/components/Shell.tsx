import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity, BarChart3, Bell, Building2, ClipboardCheck, Footprints, LayoutGrid, LogOut, Menu, Settings, ShieldCheck, Users, Video, X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ALERT_LABEL } from "../lib/format";
import { useLive, useLiveRefresh, usePulse } from "../lib/live";
import { useData } from "../lib/useData";
import type { AccessRole } from "../lib/types";
import { useToast } from "./ui";

interface NavItem { to: string; label: string; staffLabel?: string; icon: ReactNode; roles: AccessRole[] }
const NAV: NavItem[] = [
  { to: "/", label: "Overview", icon: <LayoutGrid size={18} />, roles: ["admin", "supervisor", "staff"] },
  { to: "/live", label: "Live monitoring", icon: <Video size={18} />, roles: ["admin", "supervisor"] },
  { to: "/tasks", label: "Tasks", staffLabel: "My tasks", icon: <ClipboardCheck size={18} />, roles: ["admin", "supervisor", "staff"] },
  { to: "/visits", label: "Visits", staffLabel: "My visits", icon: <Footprints size={18} />, roles: ["admin", "supervisor", "staff"] },
  { to: "/alerts", label: "Alerts", icon: <Bell size={18} />, roles: ["admin", "supervisor"] },
  { to: "/staff", label: "Staff", icon: <Users size={18} />, roles: ["admin", "supervisor"] },
  { to: "/wards", label: "Wards & cameras", icon: <Building2 size={18} />, roles: ["admin", "supervisor"] },
  { to: "/analytics", label: "Analytics", icon: <BarChart3 size={18} />, roles: ["admin", "supervisor"] },
  { to: "/audit", label: "Audit integrity", icon: <ShieldCheck size={18} />, roles: ["admin", "supervisor"] },
  { to: "/settings", label: "Settings & health", icon: <Settings size={18} />, roles: ["admin", "supervisor"] },
];

/** ECG-style trace: every live event becomes a beat travelling across the line. */
function WardPulse() {
  const beats = usePulse();
  const { status } = useLive();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 90);
    return () => window.clearInterval(id);
  }, []);
  const W = 210, H = 34, mid = H / 2, span = 12000;
  let d = `M0 ${mid}`;
  const xs = beats.map((t) => W - ((now - t) / span) * W).filter((x) => x > 0 && x < W).sort((a, b) => a - b);
  let cursor = 0;
  for (const x of xs) {
    if (x - 10 < cursor) continue;
    d += ` L${x - 10} ${mid} L${x - 7} ${mid - 3} L${x - 4} ${mid} L${x - 2} ${mid + 4} L${x + 1} ${mid - 14} L${x + 4} ${mid + 9} L${x + 7} ${mid} L${x + 11} ${mid - 2} L${x + 14} ${mid}`;
    cursor = x + 14;
  }
  d += ` L${W} ${mid}`;
  const live = status === "live";
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/80 bg-white/55 px-3 py-1.5 shadow-glass backdrop-blur-xl"
      title="Each spike is a live event from the monitoring pipeline">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-label="Live activity trace" className="hidden sm:block">
        <defs>
          <linearGradient id="pulse-fade" x1="0" x2="1">
            <stop offset="0" stopColor="#0B7A83" stopOpacity="0.05" />
            <stop offset="0.75" stopColor="#0B7A83" stopOpacity="0.85" />
            <stop offset="1" stopColor="#2EC4A0" stopOpacity="1" />
          </linearGradient>
        </defs>
        <path d={d} fill="none" stroke={live ? "url(#pulse-fade)" : "#B9C6D1"} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={W - 2} cy={mid} r="3" fill={live ? "#2EC4A0" : "#B9C6D1"}>
          {live && <animate attributeName="r" values="2.5;4;2.5" dur="1.6s" repeatCount="indefinite" />}
        </circle>
      </svg>
      <span className={clsx("text-[13px] font-semibold", live ? "text-teal" : "text-amber")}>
        {live ? "Live" : status === "connecting" ? "Connecting" : "Reconnecting"}
      </span>
    </div>
  );
}

function SideNav({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const { data: ov, reload } = useData<{ alerts_open?: number }>(user?.access_role === "staff" ? null : "/analytics/overview");
  useLiveRefresh(["alert."], reload, 2000);
  const items = NAV.filter((n) => user && n.roles.includes(user.access_role));
  return (
    <nav className="flex flex-col gap-1" aria-label="Main">
      {items.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.to === "/"} onClick={onNavigate}
          className={({ isActive }) => clsx(
            "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14.5px] font-medium transition-colors",
            isActive ? "text-teal-deep" : "text-ink-soft hover:bg-white/60 hover:text-ink")}>
          {({ isActive }) => (
            <>
              {isActive && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-xl bg-white shadow-[0_8px_20px_-14px_rgba(11,122,131,0.7)]" transition={{ type: "spring", stiffness: 500, damping: 38 }} />}
              <span className="relative">{n.icon}</span>
              <span className="relative flex-1">{user?.access_role === "staff" && n.staffLabel ? n.staffLabel : n.label}</span>
              {n.to === "/alerts" && !!ov?.alerts_open && (
                <span className="relative grid h-5 min-w-5 place-items-center rounded-full bg-coral px-1.5 text-[11px] font-bold text-white num">{ov.alerts_open}</span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export default function Shell() {
  const { user, logout } = useAuth();
  const { subscribe } = useLive();
  const toast = useToast();
  const [menu, setMenu] = useState(false);
  const loc = useLocation();
  useEffect(() => setMenu(false), [loc.pathname]);

  useEffect(() => subscribe((m) => {
    if (m.type === "alert.created" && user?.access_role !== "staff") {
      toast({ tone: "warn", title: ALERT_LABEL[m.data.alert_type] ?? "New alert", body: m.data.message });
    }
    if (m.type === "task.updated" && m.data.status === "verified") {
      toast({ tone: "ok", title: "Task verified", body: `${m.data.title} (${m.data.staff_name})` });
    }
  }), [subscribe, toast, user]);

  const brand = (
    <div className="flex items-center gap-3 px-2">
      <div className="grid h-10 w-10 place-items-center rounded-2xl bg-teal text-white shadow-clay"><Activity size={20} /></div>
      <div>
        <p className="font-display text-[17px] font-semibold leading-none tracking-[-0.02em]">IntelliWard</p>
        <p className="mt-1 text-xs text-ink-faint">Ward accountability</p>
      </div>
    </div>
  );

  const account = user && (
    <div className="mt-auto rounded-2xl border border-white/80 bg-white/50 p-3">
      <p className="truncate text-sm font-semibold">{user.full_name}</p>
      <p className="text-xs text-ink-faint">{user.access_role === "staff" ? "Staff account" : user.access_role === "admin" ? "Administrator" : "Supervisor"}</p>
      <button onClick={logout} className="mt-2 inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-soft hover:text-coral">
        <LogOut size={14} /> Sign out
      </button>
    </div>
  );

  return (
    <div className="flex min-h-full">
      <div className="canvas-field" />
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col gap-6 p-4 lg:flex">
        <div className="glass flex h-full flex-col gap-6 p-4">{brand}<SideNav />{account}</div>
      </aside>

      <AnimatePresence>
        {menu && (
          <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-ink/20 backdrop-blur-sm" onClick={() => setMenu(false)} />
            <motion.aside initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} transition={{ type: "spring", stiffness: 380, damping: 36 }}
              className="glass-strong absolute bottom-3 left-3 top-3 flex w-64 flex-col gap-6 p-4">
              <div className="flex items-center justify-between">{brand}<button onClick={() => setMenu(false)} aria-label="Close menu" className="p-1"><X size={18} /></button></div>
              <SideNav onNavigate={() => setMenu(false)} />{account}
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 px-4 pb-2 pt-4 lg:px-6">
          <button className="glass grid h-10 w-10 place-items-center lg:hidden" onClick={() => setMenu(true)} aria-label="Open menu"><Menu size={18} /></button>
          <div className="flex-1" />
          <WardPulse />
        </header>
        <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 pb-10 pt-2 lg:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="h-page">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-[15px] text-ink-soft">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
