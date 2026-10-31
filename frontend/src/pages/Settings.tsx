import { Cpu, Database, Server, Video } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "../components/Shell";
import { Badge, Button, ErrorNote, Field, Panel, PanelHead, Skeleton, StatusBadge, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ROLE_LABEL } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useData } from "../lib/useData";
import type { Camera, Settings } from "../lib/types";

interface Health { api: string; database: string; database_engine: string; worker: string; worker_last_seen_seconds: number | null; worker_info: { detector?: string; tracker?: string; face_model?: string; device?: string; cameras?: Record<string, { fps: number; latency_ms: number; error: string | null; mode: string }> }; cameras: Camera[] }

const NUMERIC: [string, string, string, number][] = [
  ["face_match_threshold", "Face match threshold (ArcFace)", "Cosine similarity. Higher means fewer false matches and more unknowns.", 0.01],
  ["face_match_threshold_sface", "Face match threshold (OpenCV SFace)", "Used when InsightFace is not installed.", 0.01],
  ["identity_votes_required", "Consistent matches before verification", "", 1],
  ["face_min_size", "Minimum face size (px)", "Smaller faces are skipped by the quality gate.", 1],
  ["visit_confirm_seconds", "Seconds before a visit is confirmed", "", 1],
  ["visit_exit_timeout_seconds", "Seconds unseen before exit", "", 1],
  ["visit_merge_window_seconds", "Re-entry merge window (s)", "Returning within this time continues the same visit.", 1],
  ["unknown_alert_seconds", "Unknown person alert after (s)", "", 1],
  ["role_mismatch_observations", "Uniform mismatches before alert", "", 1],
  ["frame_stride", "Process every Nth frame", "Raise on slower hardware.", 1],
  ["detector_confidence", "Person detector confidence", "", 0.05],
  ["retention_days", "Evidence retention (days)", "", 1],
];
const COLORS = ["blue", "white", "green", "orange"];

export default function SettingsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const s = useData<Settings>("/settings");
  const h = useData<Health>("/system/health");
  const [draft, setDraft] = useState<Settings | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (s.data) setDraft(s.data); }, [s.data]);
  useLiveRefresh(["worker.", "camera."], h.reload, 4000);
  const admin = can("admin");

  const save = async () => {
    if (!draft || !s.data) return;
    const changes = Object.fromEntries(Object.entries(draft).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(s.data![k])));
    if (!Object.keys(changes).length) { toast({ tone: "info", title: "No changes to save" }); return; }
    setBusy(true); setErr(null);
    try { s.setData(await api<Settings>("/settings", { method: "PATCH", json: changes })); toast({ tone: "ok", title: "Settings saved", body: "The vision worker applies them within a few seconds." }); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  const hd = h.data;
  return (
    <>
      <PageHeader title="Settings & health" subtitle="Recognition thresholds, visit rules and the status of every service."
        actions={admin && <Button busy={busy} onClick={save}>Save settings</Button>} />
      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <Panel>
          <PanelHead title="Monitoring rules" hint={admin ? undefined : "Only administrators can change these values."} />
          {!draft ? <div className="p-5"><Skeleton className="h-64" /></div> : (
            <div className="grid gap-4 p-5 md:grid-cols-2">
              {NUMERIC.map(([key, label, hint, step]) => (
                <Field key={key} label={label} hint={hint || undefined}>
                  <input className="field num" type="number" step={step} disabled={!admin} value={String(draft[key] ?? "")}
                    onChange={(e) => setDraft({ ...draft, [key]: step < 1 ? Number(e.target.value) : Math.round(Number(e.target.value)) })} />
                </Field>
              ))}
              <div className="md:col-span-2">
                <span className="label">Expected uniform colour per role (secondary consistency cue only)</span>
                <div className="grid gap-3 sm:grid-cols-4">
                  {Object.keys(ROLE_LABEL).map((role) => (
                    <Field key={role} label={ROLE_LABEL[role]}>
                      <select className="field" disabled={!admin} value={draft.role_color_map?.[role] ?? ""}
                        onChange={(e) => setDraft({ ...draft, role_color_map: { ...draft.role_color_map, [role]: e.target.value } })}>
                        {COLORS.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </Field>
                  ))}
                </div>
              </div>
              {err && <div className="md:col-span-2"><ErrorNote message={err} /></div>}
            </div>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel>
            <PanelHead title="Services" />
            {!hd ? <div className="p-5"><Skeleton className="h-32" /></div> : (
              <ul className="space-y-2 p-4 text-sm">
                <li className="flex items-center gap-3"><Server size={16} className="text-ink-soft" /><span className="flex-1">API</span><Badge tone="mint" dot>Running</Badge></li>
                <li className="flex items-center gap-3"><Database size={16} className="text-ink-soft" /><span className="flex-1">Database ({hd.database_engine})</span><Badge tone={hd.database === "ok" ? "mint" : "coral"} dot>{hd.database === "ok" ? "Connected" : "Error"}</Badge></li>
                <li className="flex items-center gap-3"><Cpu size={16} className="text-ink-soft" /><span className="flex-1">Vision worker</span><Badge tone={hd.worker === "online" ? "mint" : "coral"} dot>{hd.worker === "online" ? "Online" : "Offline"}</Badge></li>
                {hd.worker === "online" && (
                  <li className="rounded-xl bg-white/55 p-3 text-xs text-ink-soft">
                    <p>Detector: <b>{hd.worker_info.detector}</b></p>
                    <p>Face model: <b>{hd.worker_info.face_model}</b></p>
                    <p>Device: <b>{hd.worker_info.device}</b></p>
                  </li>
                )}
                {hd.worker !== "online" && <li className="rounded-xl bg-amber-tint/70 p-3 text-xs text-[#9a5c06]">Start it from the project folder with <code>python run.py dev</code> or <code>cd vision-worker && python worker.py</code>.</li>}
              </ul>
            )}
          </Panel>
          <Panel>
            <PanelHead title="Cameras" />
            <ul className="space-y-2 p-4">
              {hd?.cameras.map((c) => {
                const w = hd.worker_info.cameras?.[c.code];
                return (
                  <li key={c.id} className="rounded-xl bg-white/55 p-3 text-sm">
                    <div className="flex items-center gap-2"><Video size={15} className="text-ink-soft" /><span className="flex-1 font-semibold">{c.code}</span><StatusBadge status={c.status} /></div>
                    {w && <p className="mt-1 text-xs text-ink-faint num">{w.fps} fps, {w.latency_ms} ms per frame{w.mode ? `, ${w.mode}` : ""}</p>}
                    {w?.error && <p className="mt-1 text-xs text-coral">{w.error}</p>}
                  </li>
                );
              })}
            </ul>
          </Panel>
        </div>
      </div>
    </>
  );
}
