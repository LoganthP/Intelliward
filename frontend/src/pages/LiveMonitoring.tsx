import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { Play, Radio, Square, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import CameraFeed from "../components/CameraFeed";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Empty, ErrorNote, Panel, PanelHead, Skeleton, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ALERT_LABEL, ROLE_LABEL, time } from "../lib/format";
import { useLive, useLiveRefresh } from "../lib/live";
import { useData } from "../lib/useData";
import type { Camera, LiveTrack } from "../lib/types";

interface FeedItem { id: number; at: number; text: string; tone: "teal" | "coral" | "mint" | "sky" | "amber" }
const COLOR_DOT: Record<string, string> = { blue: "#3B82F6", white: "#E5E7EB", green: "#22A06B", orange: "#F59E0B", gray: "#9CA3AF", unknown: "#CBD5E1" };

export default function LiveMonitoring() {
  const { can } = useAuth();
  const toast = useToast();
  const cams = useData<Camera[]>("/cameras");
  const { subscribe } = useLive();
  const [selected, setSelected] = useState<string | null>(null);
  const [tracks, setTracks] = useState<Record<string, LiveTrack[]>>({});
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [busy, setBusy] = useState(false);
  useLiveRefresh(["camera."], cams.reload, 800);

  useEffect(() => {
    if (!selected && cams.data?.length) setSelected((cams.data.find((c) => c.enabled) ?? cams.data[0]).code);
  }, [cams.data, selected]);

  useEffect(() => subscribe((m) => {
    if (m.type === "monitoring.tracks") {
      setTracks((t) => ({ ...t, [m.data.camera_id]: m.data.tracks }));
      return;
    }
    const d = m.data;
    const add = (text: string, tone: FeedItem["tone"]) =>
      setFeed((f) => [{ id: Date.now() + Math.random(), at: Date.now(), text, tone }, ...f].slice(0, 40));
    if (m.type === "visit.started") add(`${d.staff_name} entered ${d.ward_name}`, "teal");
    else if (m.type === "visit.ended") add(`${d.staff_name} left ${d.ward_name} after ${Math.round(d.duration_seconds)}s`, "sky");
    else if (m.type === "alert.created") add(`${ALERT_LABEL[d.alert_type] ?? d.alert_type}: ${d.message}`, "coral");
    else if (m.type === "task.updated") add(`Task "${d.title}" is now ${d.status.replace("_", " ")}`, d.status === "verified" ? "mint" : "amber");
  }), [subscribe]);

  const cam = cams.data?.find((c) => c.code === selected);
  const live = (selected && tracks[selected]) || [];

  const toggle = async (c: Camera) => {
    setBusy(true);
    try {
      await api(`/cameras/${c.id}/${c.enabled ? "stop" : "start"}`, { method: "POST" });
      toast({ tone: "ok", title: c.enabled ? `${c.code} stopped` : `${c.code} starting`, body: c.enabled ? undefined : "The vision worker picks it up within a few seconds." });
      cams.reload();
    } catch (e) { toast({ tone: "warn", title: "Camera not changed", body: (e as Error).message }); }
    finally { setBusy(false); }
  };

  return (
    <>
      <PageHeader title="Live monitoring" subtitle="Annotated camera feeds with the identity state of every tracked person." />
      {cams.error && <ErrorNote message={cams.error} onRetry={cams.reload} />}
      <div className="mb-4 flex flex-wrap gap-2">
        {cams.loading && <Skeleton className="h-10 w-64" />}
        {cams.data?.map((c) => (
          <button key={c.code} onClick={() => setSelected(c.code)}
            className={clsx("flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition",
              selected === c.code ? "border-teal/30 bg-white text-ink shadow-glass" : "border-white/70 bg-white/45 text-ink-soft hover:bg-white/70")}>
            <span className={clsx("h-2 w-2 rounded-full", c.status === "online" ? "bg-mint" : c.status === "offline" ? "bg-coral" : c.enabled ? "bg-amber" : "bg-ink/20")} />
            {c.code}<span className="text-ink-faint">{c.ward_name}</span>
          </button>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel className="p-3">
          {cam ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 px-2 pb-3 pt-1">
                <div>
                  <h2 className="h-card">{cam.name}</h2>
                  <p className="text-[13px] text-ink-faint">{cam.ward_name}, source {cam.source === "sim" ? "simulated scenario" : cam.source.length > 40 ? "uploaded video" : cam.source === "0" ? "webcam 0" : cam.source}</p>
                </div>
                {can("admin", "supervisor") && (
                  <Button variant={cam.enabled ? "soft" : "primary"} busy={busy} icon={cam.enabled ? <Square size={15} /> : <Play size={15} />} onClick={() => toggle(cam)}>
                    {cam.enabled ? "Stop camera" : "Start camera"}
                  </Button>
                )}
              </div>
              <CameraFeed camera={cam} />
              {cam.error && <p className="mt-2 px-2 text-sm text-coral">{cam.error}</p>}
            </>
          ) : <Skeleton className="aspect-video w-full" />}
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHead title="Tracked people" hint={live.length ? `${live.length} in view` : "Nobody in view"} />
            <div className="p-3">
              {live.length === 0 ? <Empty icon={<UserRound size={20} />} title="No one tracked" body="People appear here as the worker detects them." /> : (
                <ul className="space-y-1.5">
                  <AnimatePresence initial={false}>
                    {live.map((t) => (
                      <motion.li key={t.track_id} layout initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                        className="flex items-center gap-3 rounded-xl bg-white/55 px-3 py-2">
                        <span className="h-3 w-3 shrink-0 rounded-full ring-2 ring-white" style={{ background: COLOR_DOT[t.role_color ?? "unknown"] ?? "#CBD5E1" }} title={`Uniform cue: ${t.role_color ?? "unknown"}`} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold">
                            {t.identity_status === "verified" ? `${t.staff_name}` : t.identity_status === "unknown" ? "Unrecognized person" : "Identifying"}
                          </p>
                          <p className="truncate text-xs text-ink-faint">
                            {t.identity_status === "verified" ? `${t.staff_code}, ${ROLE_LABEL[t.role ?? ""] ?? t.role}` : `Track ${t.track_id}`}{t.zone ? `, ${t.zone} zone` : ""}
                          </p>
                        </div>
                        <Badge tone={t.identity_status === "verified" ? "mint" : t.identity_status === "unknown" ? "coral" : "amber"}>
                          {t.identity_status === "verified" ? `${Math.round(t.similarity * 100)}` : t.identity_status}
                        </Badge>
                      </motion.li>
                    ))}
                  </AnimatePresence>
                </ul>
              )}
              {live.some((t) => t.identity_status === "verified") && (
                <p className="mt-2 px-1 text-[11.5px] text-ink-faint">The number is the model's match score, not a calibrated probability.</p>
              )}
            </div>
          </Panel>
          <Panel className="flex-1">
            <PanelHead title="Event stream" hint="Visits, alerts and task changes as they happen" />
            <ul className="max-h-[360px] space-y-1 overflow-y-auto p-3">
              {feed.length === 0 && <Empty icon={<Radio size={20} />} title="Listening for events" />}
              {feed.map((f) => (
                <li key={f.id} className="flex gap-3 rounded-xl px-2 py-1.5 text-[13px]">
                  <span className="shrink-0 text-ink-faint num">{time(new Date(f.at).toISOString())}</span>
                  <span className={clsx("flex-1", f.tone === "coral" && "text-[#b42a2f]")}>{f.text}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </>
  );
}
