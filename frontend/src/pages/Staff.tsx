import { Camera as CameraIcon, ImagePlus, Plus, ScanFace, Trash2, Users } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Empty, ErrorNote, Field, Modal, Panel, Skeleton, Table, Toggle, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ROLE_LABEL } from "../lib/format";
import { useLive, useLiveRefresh } from "../lib/live";
import { useData } from "../lib/useData";
import type { Staff, Ward } from "../lib/types";

export default function StaffPage() {
  const { can } = useAuth();
  const staff = useData<Staff[]>("/staff");
  const wards = useData<Ward[]>("/wards");
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Staff | null>(null);
  const [enrolling, setEnrolling] = useState<Staff | null>(null);
  useLiveRefresh(["staff."], staff.reload, 500);
  const wardName = (id: number) => wards.data?.find((w) => w.id === id)?.code ?? id;

  return (
    <>
      <PageHeader title="Staff" subtitle="Registered personnel, their ward access and face enrollment status."
        actions={can("admin", "supervisor") && <Button icon={<Plus size={16} />} onClick={() => setAdding(true)}>Add staff member</Button>} />
      {staff.error && <ErrorNote message={staff.error} onRetry={staff.reload} />}
      <Panel>
        {staff.loading ? <div className="p-5"><Skeleton className="h-40" /></div> : (
          <Table head={["Staff", "Role", "Ward access", "Face template", "Status", ""]}
            empty={staff.data?.length === 0 && <Empty icon={<Users size={20} />} title="No staff registered yet" action={<Button onClick={() => setAdding(true)}>Add staff member</Button>} />}>
            {staff.data?.map((s) => (
              <tr key={s.id} className="hover:bg-white/40">
                <td className="px-5 py-3"><p className="font-semibold">{s.name}</p><p className="text-xs text-ink-faint">{s.staff_code}{s.department ? `, ${s.department}` : ""}</p></td>
                <td className="px-5 py-3">{ROLE_LABEL[s.role] ?? s.role}</td>
                <td className="px-5 py-3"><div className="flex flex-wrap gap-1">{s.ward_ids.map((w) => <Badge key={w}>{wardName(w)}</Badge>)}</div></td>
                <td className="px-5 py-3">
                  {s.enrolled ? <Badge tone="mint" dot>Enrolled</Badge>
                    : s.enrollment_images ? <Badge tone="amber" dot>Processing {s.enrollment_images} images</Badge>
                    : <Badge>Not enrolled</Badge>}
                  {!s.consent_recorded && <p className="mt-1 text-xs text-ink-faint">Consent not recorded</p>}
                </td>
                <td className="px-5 py-3"><Badge tone={s.active ? "teal" : "slate"}>{s.active ? "Active" : "Inactive"}</Badge></td>
                <td className="px-5 py-3 text-right">
                  <div className="flex justify-end gap-1">
                    <Button size="sm" variant="soft" icon={<ScanFace size={14} />} onClick={() => setEnrolling(s)}>Enroll face</Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditing(s)}>Edit</Button>
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
      <StaffForm open={adding} onClose={() => setAdding(false)} wards={wards.data ?? []} onSaved={staff.reload} />
      <StaffForm open={!!editing} existing={editing} onClose={() => setEditing(null)} wards={wards.data ?? []} onSaved={staff.reload} />
      <EnrollModal staff={enrolling} onClose={() => setEnrolling(null)} onDone={staff.reload} />
    </>
  );
}

function StaffForm({ open, onClose, wards, onSaved, existing }: { open: boolean; onClose: () => void; wards: Ward[]; onSaved: () => void; existing?: Staff | null }) {
  const toast = useToast();
  const [f, setF] = useState({ staff_code: "", name: "", role: "nurse", department: "", consent_recorded: false, ward_ids: [] as number[], create_login: false, password: "", active: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!open) return;
    setError(null);
    setF(existing ? { staff_code: existing.staff_code, name: existing.name, role: existing.role, department: existing.department, consent_recorded: existing.consent_recorded, ward_ids: existing.ward_ids, create_login: false, password: "", active: existing.active }
      : { staff_code: "", name: "", role: "nurse", department: "", consent_recorded: false, ward_ids: [], create_login: false, password: "", active: true });
  }, [open, existing]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      if (existing) {
        await api(`/staff/${existing.id}`, { method: "PATCH", json: { name: f.name, role: f.role, department: f.department, consent_recorded: f.consent_recorded, ward_ids: f.ward_ids, active: f.active } });
        toast({ tone: "ok", title: "Staff member updated" });
      } else {
        await api("/staff", { method: "POST", json: { ...f, password: f.create_login ? f.password : null } });
        toast({ tone: "ok", title: "Staff member added", body: f.consent_recorded ? "Next, enroll their face images." : "Record consent before enrolling face images." });
      }
      onSaved(); onClose();
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title={existing ? `Edit ${existing.name}` : "Add staff member"}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Staff code"><input className="field" value={f.staff_code} disabled={!!existing} onChange={(e) => setF({ ...f, staff_code: e.target.value })} placeholder="NUR-002" required /></Field>
        <Field label="Full name"><input className="field" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
        <Field label="Registered role">
          <select className="field" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
            {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
        <Field label="Department"><input className="field" value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} /></Field>
        <div className="sm:col-span-2">
          <span className="label">Authorized wards</span>
          <div className="flex flex-wrap gap-2">
            {wards.map((w) => {
              const on = f.ward_ids.includes(w.id);
              return (
                <button type="button" key={w.id} onClick={() => setF({ ...f, ward_ids: on ? f.ward_ids.filter((x) => x !== w.id) : [...f.ward_ids, w.id] })}
                  className={`rounded-full border px-3 py-1 text-[13px] font-medium ${on ? "border-teal bg-teal-tint text-teal-deep" : "border-ink/10 bg-white/70 text-ink-soft"}`}>
                  {w.name}{w.restricted ? " (restricted)" : ""}
                </button>
              );
            })}
          </div>
        </div>
        <div className="sm:col-span-2 space-y-3 rounded-2xl bg-ink/[0.03] p-3">
          <Toggle checked={f.consent_recorded} onChange={(v) => setF({ ...f, consent_recorded: v })} label="Written consent for biometric enrollment recorded" />
          {existing && <Toggle checked={f.active} onChange={(v) => setF({ ...f, active: v })} label="Active staff member" />}
          {!existing && <Toggle checked={f.create_login} onChange={(v) => setF({ ...f, create_login: v })} label="Create a staff login (username is the staff code)" />}
          {!existing && f.create_login && <input className="field" type="password" placeholder="Initial password, 6+ characters" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />}
        </div>
        {error && <div className="sm:col-span-2"><ErrorNote message={error} /></div>}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" busy={busy}>{existing ? "Save changes" : "Add staff member"}</Button>
        </div>
      </form>
    </Modal>
  );
}

function EnrollModal({ staff, onClose, onDone }: { staff: Staff | null; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const { can } = useAuth();
  const { subscribe } = useLive();
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [shots, setShots] = useState<Blob[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [camOn, setCamOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const stopCam = () => { streamRef.current?.getTracks().forEach((t) => t.stop()); streamRef.current = null; setCamOn(false); };
  useEffect(() => {
    if (!staff) { stopCam(); setShots([]); setPreviews((p) => { p.forEach(URL.revokeObjectURL); return []; }); setError(null); setResult(null); }
  }, [staff]);
  useEffect(() => stopCam, []);
  useEffect(() => subscribe((m) => {
    if (m.type === "staff.updated" && staff && m.data.id === staff.id && m.data.enrollment_result) {
      const r = m.data.enrollment_result;
      setResult(r.usable_images ? `Face template ready from ${r.usable_images} usable image(s)${r.rejected_images ? `, ${r.rejected_images} rejected` : ""}.`
        : "No usable face found. Retake photos facing the camera in good light, one person per photo.");
    }
  }), [subscribe, staff]);

  const startCam = async () => {
    setError(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
      streamRef.current = s;
      if (videoRef.current) { videoRef.current.srcObject = s; await videoRef.current.play(); }
      setCamOn(true);
    } catch {
      setError("Browser camera unavailable. If the vision worker is using the same webcam, stop CAM-01 first, or upload photos instead.");
    }
  };
  const addBlob = (b: Blob) => { setShots((s) => [...s, b].slice(0, 10)); setPreviews((p) => [...p, URL.createObjectURL(b)].slice(0, 10)); };
  const capture = () => {
    const v = videoRef.current;
    if (!v) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d")!.drawImage(v, 0, 0);
    c.toBlob((b) => b && addBlob(b), "image/jpeg", 0.92);
  };

  const upload = async () => {
    if (!staff) return;
    setBusy(true); setError(null);
    const fd = new FormData();
    shots.forEach((b, i) => fd.append("files", b, `capture-${i}.jpg`));
    try {
      await api(`/staff/${staff.id}/enroll`, { method: "POST", body: fd });
      toast({ tone: "info", title: "Images stored", body: "The vision worker is building the face template." });
      setResult("Waiting for the vision worker to compute the face template...");
      stopCam(); onDone();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const clear = async () => {
    if (!staff) return;
    try { await api(`/staff/${staff.id}/enrollment`, { method: "DELETE" }); toast({ tone: "ok", title: "Enrollment deleted" }); onDone(); onClose(); }
    catch (e) { setError((e as Error).message); }
  };

  return (
    <Modal open={!!staff} onClose={onClose} title={staff ? `Face enrollment for ${staff.name}` : ""} wide>
      {staff && !staff.consent_recorded ? (
        <Empty icon={<ScanFace size={20} />} title="Consent required" body="Record this person's written consent in Edit before collecting face images." />
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-ink-soft">Capture 3 to 6 clear photos: face the camera, good light, slight head turns, one person per photo. Images are stored on the hospital server; only the encrypted template is used for matching.</p>
          <div className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
            <div className="overflow-hidden rounded-2xl bg-[#e7eef3]">
              <video ref={videoRef} className={camOn ? "aspect-video w-full object-cover" : "hidden"} muted playsInline />
              {!camOn && <div className="grid aspect-video place-items-center text-sm text-ink-faint">Camera preview</div>}
            </div>
            <div className="flex flex-col gap-2">
              {!camOn ? <Button variant="soft" icon={<CameraIcon size={16} />} onClick={startCam}>Use browser camera</Button>
                : <Button icon={<CameraIcon size={16} />} onClick={capture} disabled={shots.length >= 10}>Capture photo</Button>}
              <label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border border-ink/10 bg-white/80 text-sm font-semibold hover:bg-white">
                <ImagePlus size={16} /> Upload photos
                <input type="file" accept="image/jpeg,image/png" multiple className="hidden" onChange={(e) => Array.from(e.target.files ?? []).forEach(addBlob)} />
              </label>
              <div className="grid grid-cols-4 gap-1.5">
                {previews.map((p, i) => <img key={p} src={p} alt={`Capture ${i + 1}`} className="aspect-square rounded-lg object-cover" />)}
              </div>
            </div>
          </div>
          {result && <div className="rounded-xl bg-teal-tint/70 px-4 py-3 text-sm text-teal-deep">{result}</div>}
          {error && <ErrorNote message={error} />}
          <div className="flex flex-wrap justify-between gap-2">
            {can("admin") && staff && staff.enrollment_images > 0 ? <Button variant="ghost" icon={<Trash2 size={15} />} onClick={clear}>Delete stored images</Button> : <span />}
            <div className="flex gap-2">
              <Button variant="ghost" onClick={onClose}>Close</Button>
              <Button busy={busy} disabled={shots.length === 0} onClick={upload}>Save {shots.length || ""} photo{shots.length === 1 ? "" : "s"}</Button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
