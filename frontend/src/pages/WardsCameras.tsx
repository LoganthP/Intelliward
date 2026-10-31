import { Building2, Lock, Plus, Trash2, Upload, Video } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Empty, ErrorNote, Field, Modal, Panel, PanelHead, Skeleton, StatusBadge, Toggle, useToast } from "../components/ui";
import { api, tokenStore } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ago } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useData } from "../lib/useData";
import type { Camera, Ward, Zone } from "../lib/types";

export default function WardsCameras() {
  const { can } = useAuth();
  const wards = useData<Ward[]>("/wards");
  const cams = useData<Camera[]>("/cameras");
  const [wardForm, setWardForm] = useState<Ward | "new" | null>(null);
  const [camForm, setCamForm] = useState<Camera | "new" | null>(null);
  useLiveRefresh(["camera."], cams.reload, 1000);
  const admin = can("admin");

  return (
    <>
      <PageHeader title="Wards & cameras" subtitle="Monitored areas, access rules, camera sources and task zones."
        actions={admin && <>
          <Button variant="soft" icon={<Plus size={16} />} onClick={() => setWardForm("new")}>Add ward</Button>
          <Button icon={<Plus size={16} />} onClick={() => setCamForm("new")}>Add camera</Button>
        </>} />
      {(wards.error || cams.error) && <ErrorNote message={(wards.error || cams.error)!} onRetry={() => { wards.reload(); cams.reload(); }} />}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {wards.loading && <Skeleton className="h-36" />}
        {wards.data?.map((w) => {
          const wc = cams.data?.filter((c) => c.ward_id === w.id) ?? [];
          return (
            <Panel key={w.id} className="p-5">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-3">
                  <div className="grid h-10 w-10 place-items-center rounded-2xl bg-sky-tint text-[#1f6bb5]"><Building2 size={18} /></div>
                  <div><p className="font-display font-semibold">{w.name}</p><p className="text-xs text-ink-faint">{w.code}{w.location ? `, ${w.location}` : ""}</p></div>
                </div>
                {admin && <Button size="sm" variant="ghost" onClick={() => setWardForm(w)}>Edit</Button>}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {w.restricted ? <Badge tone="coral"><Lock size={12} /> Restricted</Badge> : <Badge>Open access</Badge>}
                <Badge tone="sky">Stay alert after {w.prolonged_stay_minutes} min</Badge>
              </div>
              <div className="mt-4 space-y-2">
                {wc.length === 0 && <p className="text-sm text-ink-faint">No camera covers this ward.</p>}
                {wc.map((c) => (
                  <button key={c.id} onClick={() => setCamForm(c)} className="flex w-full items-center gap-3 rounded-xl bg-white/55 px-3 py-2 text-left hover:bg-white">
                    <Video size={16} className="text-ink-soft" />
                    <span className="flex-1 text-sm font-medium">{c.code} <span className="text-ink-faint">{c.name}</span></span>
                    <StatusBadge status={c.status} />
                  </button>
                ))}
              </div>
            </Panel>
          );
        })}
      </div>
      <WardModal value={wardForm} onClose={() => setWardForm(null)} onSaved={wards.reload} />
      <CameraModal value={camForm} wards={wards.data ?? []} onClose={() => setCamForm(null)} onSaved={cams.reload} readOnly={!admin} />
    </>
  );
}

function WardModal({ value, onClose, onSaved }: { value: Ward | "new" | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({ code: "", name: "", location: "", restricted: false, prolonged_stay_minutes: 60 });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setErr(null);
    if (value && value !== "new") setF({ code: value.code, name: value.name, location: value.location, restricted: value.restricted, prolonged_stay_minutes: value.prolonged_stay_minutes });
    else setF({ code: "", name: "", location: "", restricted: false, prolonged_stay_minutes: 60 });
  }, [value]);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      if (value === "new") await api("/wards", { method: "POST", json: f });
      else if (value) await api(`/wards/${value.id}`, { method: "PATCH", json: f });
      toast({ tone: "ok", title: "Ward saved" }); onSaved(); onClose();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  return (
    <Modal open={!!value} onClose={onClose} title={value === "new" ? "Add ward" : "Edit ward"}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Ward code"><input className="field" value={f.code} disabled={value !== "new"} onChange={(e) => setF({ ...f, code: e.target.value })} required /></Field>
        <Field label="Name"><input className="field" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
        <Field label="Location"><input className="field" value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} /></Field>
        <Field label="Prolonged stay alert (minutes)"><input className="field" type="number" min={1} value={f.prolonged_stay_minutes} onChange={(e) => setF({ ...f, prolonged_stay_minutes: Number(e.target.value) })} /></Field>
        <div className="sm:col-span-2"><Toggle checked={f.restricted} onChange={(v) => setF({ ...f, restricted: v })} label="Restricted ward: alert when unauthorized staff enter" /></div>
        {err && <div className="sm:col-span-2"><ErrorNote message={err} /></div>}
        <div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button busy={busy} type="submit">Save ward</Button></div>
      </form>
    </Modal>
  );
}

function CameraModal({ value, wards, onClose, onSaved, readOnly }: { value: Camera | "new" | null; wards: Ward[]; onClose: () => void; onSaved: () => void; readOnly: boolean }) {
  const toast = useToast();
  const [f, setF] = useState({ code: "", name: "", ward_id: 0, source: "0", zones: [] as Zone[] });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const existing = value && value !== "new" ? value : null;
  useEffect(() => {
    setErr(null); setFile(null);
    if (existing) setF({ code: existing.code, name: existing.name, ward_id: existing.ward_id, source: existing.source, zones: existing.zones });
    else setF({ code: "", name: "", ward_id: wards[0]?.id ?? 0, source: "0", zones: [{ name: "bedside", x1: 0, y1: 0.45, x2: 0.45, y2: 1 }, { name: "equipment", x1: 0.6, y1: 0.45, x2: 1, y2: 1 }] });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const setZone = (i: number, k: keyof Zone, v: string) => setF({ ...f, zones: f.zones.map((z, j) => j === i ? { ...z, [k]: k === "name" ? v : Math.min(1, Math.max(0, Number(v))) } : z) });

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      let cam: Camera;
      if (existing) cam = await api<Camera>(`/cameras/${existing.id}`, { method: "PATCH", json: { name: f.name, ward_id: f.ward_id, source: f.source, zones: f.zones } });
      else cam = await api<Camera>("/cameras", { method: "POST", json: f });
      if (file) {
        const fd = new FormData(); fd.append("file", file);
        await api(`/cameras/${cam.id}/video`, { method: "POST", body: fd });
      }
      toast({ tone: "ok", title: "Camera saved", body: file ? "Video uploaded and set as the source." : undefined }); onSaved(); onClose();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  const snap = existing && existing.status === "online" ? `/api/v1/cameras/${existing.code}/snapshot?token=${encodeURIComponent(tokenStore.get() ?? "")}&t=${Date.now()}` : null;

  return (
    <Modal open={!!value} onClose={onClose} title={existing ? `${existing.code} settings` : "Add camera"} wide>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Camera code"><input className="field" value={f.code} disabled={!!existing} onChange={(e) => setF({ ...f, code: e.target.value })} required /></Field>
          <Field label="Name"><input className="field" value={f.name} disabled={readOnly} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
          <Field label="Ward">
            <select className="field" value={f.ward_id} disabled={readOnly} onChange={(e) => setF({ ...f, ward_id: Number(e.target.value) })}>
              {wards.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Video source" hint='Webcam index ("0"), an RTSP URL, a video file path, or "sim" for the synthetic ward scenario.'>
          <input className="field" value={f.source} disabled={readOnly} onChange={(e) => setF({ ...f, source: e.target.value })} />
        </Field>
        {!readOnly && (
          <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-ink/15 bg-white/50 px-4 py-3 text-sm">
            <Upload size={16} className="text-teal" />
            <span className="flex-1">{file ? file.name : "Or upload an MP4 recording of the mock ward (replaces the source)"}</span>
            <input type="file" accept="video/mp4,video/*" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
        )}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="label mb-0">Task zones (fractions of the frame, foot point decides the zone)</span>
            {!readOnly && <Button type="button" size="sm" variant="soft" icon={<Plus size={14} />} onClick={() => setF({ ...f, zones: [...f.zones, { name: `zone-${f.zones.length + 1}`, x1: 0.3, y1: 0.5, x2: 0.6, y2: 1 }] })}>Add zone</Button>}
          </div>
          <div className="grid gap-4 md:grid-cols-[1fr_1fr]">
            <div className="relative aspect-video overflow-hidden rounded-xl bg-[#e7eef3]">
              {snap && <img src={snap} alt="Latest frame" className="absolute inset-0 h-full w-full object-cover opacity-80" />}
              {f.zones.map((z) => (
                <div key={z.name} className="absolute border-2 border-teal bg-teal/15" style={{ left: `${z.x1 * 100}%`, top: `${z.y1 * 100}%`, width: `${(z.x2 - z.x1) * 100}%`, height: `${(z.y2 - z.y1) * 100}%` }}>
                  <span className="m-1 inline-block rounded bg-white/90 px-1.5 text-[11px] font-semibold text-teal-deep">{z.name}</span>
                </div>
              ))}
              {!snap && f.zones.length === 0 && <Empty icon={<Video size={18} />} title="No zones" />}
            </div>
            <div className="space-y-2">
              {f.zones.map((z, i) => (
                <div key={i} className="grid grid-cols-[1.4fr_repeat(4,1fr)_auto] items-center gap-1.5">
                  <input className="field px-2" value={z.name} disabled={readOnly} onChange={(e) => setZone(i, "name", e.target.value)} aria-label="Zone name" />
                  {(["x1", "y1", "x2", "y2"] as const).map((k) => (
                    <input key={k} className="field px-2 num" type="number" step={0.05} min={0} max={1} value={z[k]} disabled={readOnly} onChange={(e) => setZone(i, k, e.target.value)} aria-label={k} />
                  ))}
                  {!readOnly && <button type="button" className="p-1 text-ink-faint hover:text-coral" onClick={() => setF({ ...f, zones: f.zones.filter((_, j) => j !== i) })} aria-label="Remove zone"><Trash2 size={15} /></button>}
                </div>
              ))}
              <p className="text-xs text-ink-faint">Columns: name, left, top, right, bottom.</p>
            </div>
          </div>
        </div>
        {existing && <p className="text-xs text-ink-faint">Last frame {ago(existing.last_frame_at)}</p>}
        {err && <ErrorNote message={err} />}
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Close</Button>{!readOnly && <Button type="submit" busy={busy}>Save camera</Button>}</div>
      </form>
    </Modal>
  );
}
