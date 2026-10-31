import { motion } from "framer-motion";
import { Bell, ClipboardCheck, Cpu, ShieldCheck, UserCheck, Video } from "lucide-react";
import { Link } from "react-router-dom";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import CameraFeed from "../components/CameraFeed";
import { PageHeader } from "../components/Shell";
import { Badge, Empty, ErrorNote, Panel, PanelHead, Progress, Skeleton, StatusBadge, severityTone } from "../components/ui";
import { useAuth } from "../lib/auth";
import { ALERT_LABEL, ROLE_LABEL, TASK_LABEL, ago, duration, time } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useData } from "../lib/useData";
import type { Alert, Camera, Task, Visit } from "../lib/types";

interface Overview {
  cameras_total: number; cameras_online: number; staff_total: number; staff_enrolled: number; staff_present: number;
  present_now: { staff_id: number; name: string; code: string; role: string; ward: string; since: string }[];
  alerts_open: number; alerts_high_open: number; tasks_verified_24h: number; tasks_open: number; tasks_review: number;
  tasks_overdue: number; visits_24h: number; avg_visit_seconds: number; audit_events: number; worker_online: boolean;
}

const tile = { hidden: { opacity: 0, y: 14, scale: 0.98 }, show: { opacity: 1, y: 0, scale: 1 } };

export default function OverviewPage() {
  const { user } = useAuth();
  return user?.access_role === "staff" ? <StaffOverview /> : <HospitalOverview />;
}

function HospitalOverview() {
  const ov = useData<Overview>("/analytics/overview");
  const cams = useData<Camera[]>("/cameras");
  const alerts = useData<Alert[]>("/alerts?status=active&limit=6");
  const tasks = useData<Task[]>("/tasks");
  const trends = useData<{ visits_by_hour: { hour: string; visits: number }[] }>("/analytics/trends?days=1");
  useLiveRefresh(["visit.", "task.", "alert.", "camera."], () => { ov.reload(); alerts.reload(); tasks.reload(); }, 1500);
  useLiveRefresh(["camera."], cams.reload, 1000);
  useLiveRefresh(["visit."], trends.reload, 5000);

  const o = ov.data;
  const featured = cams.data?.find((c) => c.status === "online") ?? cams.data?.find((c) => c.enabled) ?? cams.data?.[0];
  const activeTasks = (tasks.data ?? []).filter((t) => ["in_progress", "review_required", "pending", "overdue"].includes(t.status)).slice(0, 5);

  return (
    <>
      <PageHeader title="Ward overview" subtitle="Live presence, open work and alerts across every monitored ward." />
      {ov.error && <div className="mb-4"><ErrorNote message={ov.error} onRetry={ov.reload} /></div>}
      <motion.div className="grid auto-rows-[minmax(0,auto)] grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
        initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.06 } } }}>

        <motion.div variants={tile} className="md:col-span-2 xl:row-span-2">
          <Panel className="h-full p-3">
            <div className="flex items-center justify-between px-2 pb-3 pt-1">
              <div>
                <h2 className="h-card">{featured ? featured.name : "Live camera"}</h2>
                <p className="text-[13px] text-ink-faint">{featured?.ward_name ?? "No camera configured"}</p>
              </div>
              <Link to="/live" className="rounded-xl px-3 py-1.5 text-[13px] font-semibold text-teal hover:bg-teal-tint">Open monitoring</Link>
            </div>
            {featured ? <CameraFeed camera={featured} /> : <Skeleton className="aspect-video w-full" />}
          </Panel>
        </motion.div>

        <motion.div variants={tile}>
          <Panel className="flex h-full flex-col">
            <PanelHead title="In the wards now" hint={o ? `${o.staff_present} of ${o.staff_total} staff present` : " "} />
            <div className="flex-1 px-3 pb-3 pt-2">
              {!o ? <Skeleton className="h-28" /> : o.present_now.length === 0 ? (
                <Empty icon={<UserCheck size={20} />} title="No one verified in a ward" body="Visits appear here once a registered person is identified on camera." />
              ) : (
                <ul className="space-y-1">
                  {o.present_now.slice(0, 6).map((p) => (
                    <li key={`${p.staff_id}-${p.ward}`} className="flex items-center gap-3 rounded-xl px-2 py-1.5 hover:bg-white/60">
                      <span className="grid h-8 w-8 place-items-center rounded-full bg-teal-tint text-[12px] font-bold text-teal-deep">{p.name.split(" ").map((x) => x[0]).slice(0, 2).join("")}</span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold">{p.name}</p>
                        <p className="truncate text-xs text-ink-faint">{ROLE_LABEL[p.role] ?? p.role}, {p.ward}</p>
                      </div>
                      <span className="text-xs text-ink-faint">{ago(p.since)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </motion.div>

        <motion.div variants={tile}>
          <Panel className="flex h-full flex-col">
            <PanelHead title="Open alerts" action={<Link to="/alerts" className="text-[13px] font-semibold text-teal">Review</Link>}
              hint={o ? (o.alerts_high_open ? `${o.alerts_high_open} high severity` : "Nothing urgent") : " "} />
            <div className="px-5 pt-1"><p className="font-display text-[2.6rem] font-semibold leading-none tracking-[-0.04em] num text-ink">{o?.alerts_open ?? "–"}</p></div>
            <ul className="mt-3 flex-1 space-y-1 px-3 pb-3">
              {(alerts.data ?? []).slice(0, 3).map((a) => (
                <li key={a.id} className="flex items-start gap-2 rounded-xl px-2 py-1.5">
                  <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-semibold">{ALERT_LABEL[a.alert_type] ?? a.alert_type}</p>
                    <p className="truncate text-xs text-ink-faint">{a.ward_name ?? "Hospital"}, {ago(a.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
        </motion.div>

        <motion.div variants={tile} className="md:col-span-2">
          <Panel className="h-full">
            <PanelHead title="Task verification" action={<Link to="/tasks" className="text-[13px] font-semibold text-teal">All tasks</Link>}
              hint={o ? `${o.tasks_verified_24h} verified in 24 h, ${o.tasks_review} awaiting review, ${o.tasks_overdue} overdue` : " "} />
            <div className="space-y-3 px-5 pb-5 pt-3">
              {tasks.loading && <Skeleton className="h-20" />}
              {!tasks.loading && activeTasks.length === 0 && <Empty icon={<ClipboardCheck size={20} />} title="No open tasks" body="Assign ward work from the Tasks page." />}
              {activeTasks.map((t) => (
                <div key={t.id} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1.5">
                  <p className="truncate text-sm font-semibold">{t.title} <span className="font-normal text-ink-faint">, {t.staff_name}</span></p>
                  <StatusBadge status={t.status} />
                  <Progress value={t.progress} tone={t.status === "review_required" ? "amber" : "teal"} />
                  <span className="text-xs text-ink-faint num">{Math.round(t.accumulated_seconds)}/{t.min_duration_sec}s</span>
                </div>
              ))}
            </div>
          </Panel>
        </motion.div>

        <motion.div variants={tile} className="md:col-span-2">
          <Panel className="h-full">
            <PanelHead title="Ward visits, last 24 hours" hint={o ? `${o.visits_24h} visits, average stay ${duration(o.avg_visit_seconds)}` : " "} />
            <div className="h-40 px-2 pb-3">
              <ResponsiveContainer>
                <AreaChart data={(trends.data?.visits_by_hour ?? []).map((h) => ({ ...h, label: time(h.hour).slice(0, 5) }))} margin={{ top: 10, right: 12, left: 12, bottom: 0 }}>
                  <defs>
                    <linearGradient id="visitsFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0" stopColor="#2EC4A0" stopOpacity={0.45} /><stop offset="1" stopColor="#2EC4A0" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#7F98AD" }} axisLine={false} tickLine={false} interval={3} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(255,255,255,.8)", boxShadow: "0 10px 30px -12px rgba(15,46,68,.3)" }} />
                  <Area type="monotone" dataKey="visits" stroke="#0B7A83" strokeWidth={2} fill="url(#visitsFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </motion.div>

        <motion.div variants={tile}>
          <Panel className="h-full p-5">
            <div className="flex items-center gap-2 text-ink-soft"><Video size={16} /><span className="text-[13px] font-medium">Cameras</span></div>
            <p className="mt-2 font-display text-3xl font-semibold tracking-[-0.03em] num">{o ? `${o.cameras_online}/${o.cameras_total}` : "–"}</p>
            <p className="text-[13px] text-ink-faint">streaming now</p>
            <div className="mt-4 flex items-center gap-2 text-ink-soft"><Cpu size={16} /><span className="text-[13px] font-medium">Vision worker</span></div>
            <div className="mt-1.5">{o ? <Badge tone={o.worker_online ? "mint" : "coral"} dot>{o.worker_online ? "Running" : "Not connected"}</Badge> : null}</div>
          </Panel>
        </motion.div>

        <motion.div variants={tile}>
          <Panel className="h-full p-5">
            <div className="flex items-center gap-2 text-ink-soft"><ShieldCheck size={16} /><span className="text-[13px] font-medium">Audit trail</span></div>
            <p className="mt-2 font-display text-3xl font-semibold tracking-[-0.03em] num">{o?.audit_events ?? "–"}</p>
            <p className="text-[13px] text-ink-faint">hash-chained events</p>
            <Link to="/audit" className="mt-4 inline-block text-[13px] font-semibold text-teal">Verify integrity</Link>
          </Panel>
        </motion.div>
      </motion.div>
    </>
  );
}

function StaffOverview() {
  const { user } = useAuth();
  const ov = useData<{ tasks_open: number; tasks_verified_24h: number; visits_24h: number; present: boolean }>("/analytics/overview");
  const tasks = useData<Task[]>("/tasks");
  const visits = useData<Visit[]>("/visits?limit=6");
  useLiveRefresh(["task.", "visit."], () => { ov.reload(); tasks.reload(); visits.reload(); });
  const open = (tasks.data ?? []).filter((t) => !["verified", "rejected"].includes(t.status));
  return (
    <>
      <PageHeader title={`Hello, ${user?.full_name.split(" ")[0]}`} subtitle="Your assigned ward work and recorded visits." />
      <div className="grid gap-4 md:grid-cols-3">
        <Panel className="p-5">
          <p className="text-[13px] text-ink-soft">Presence</p>
          <div className="mt-2">{ov.data && <Badge tone={ov.data.present ? "teal" : "slate"} dot>{ov.data.present ? "Recorded in a ward" : "Not in a monitored ward"}</Badge>}</div>
        </Panel>
        <Panel className="p-5"><p className="text-[13px] text-ink-soft">Open tasks</p><p className="mt-1 font-display text-3xl font-semibold num">{ov.data?.tasks_open ?? "–"}</p></Panel>
        <Panel className="p-5"><p className="text-[13px] text-ink-soft">Verified today</p><p className="mt-1 font-display text-3xl font-semibold num">{ov.data?.tasks_verified_24h ?? "–"}</p></Panel>
        <Panel className="md:col-span-2">
          <PanelHead title="My open tasks" />
          <div className="space-y-4 p-5">
            {open.length === 0 && <Empty icon={<ClipboardCheck size={20} />} title="Nothing assigned right now" />}
            {open.map((t) => (
              <div key={t.id}>
                <div className="mb-1.5 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold">{t.title} <span className="font-normal text-ink-faint">, {TASK_LABEL[t.task_type]} in {t.ward_name}{t.zone ? ` (${t.zone} zone)` : ""}</span></p>
                  <StatusBadge status={t.status} />
                </div>
                <Progress value={t.progress} />
              </div>
            ))}
          </div>
        </Panel>
        <Panel>
          <PanelHead title="Recent visits" />
          <ul className="space-y-1 p-3">
            {(visits.data ?? []).map((v) => (
              <li key={v.id} className="flex justify-between rounded-xl px-2 py-1.5 text-sm"><span>{v.ward_name}</span><span className="text-ink-faint num">{duration(v.duration_seconds)}</span></li>
            ))}
            {visits.data?.length === 0 && <Empty icon={<Bell size={20} />} title="No visits recorded yet" />}
          </ul>
        </Panel>
      </div>
    </>
  );
}
