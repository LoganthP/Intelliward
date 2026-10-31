import clsx from "clsx";
import { CheckCircle2, ClipboardCheck, Plus, XCircle } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Empty, ErrorNote, Field, Modal, Panel, Progress, Skeleton, StatusBadge, Toggle, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ROLE_LABEL, TASK_LABEL, dateTime, pretty, time } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useData } from "../lib/useData";
import type { Staff, Task, Ward } from "../lib/types";

const FILTERS: [string, string, (t: Task) => boolean][] = [
  ["open", "Open", (t) => ["pending", "in_progress", "overdue"].includes(t.status)],
  ["review", "Needs review", (t) => t.status === "review_required"],
  ["done", "Verified", (t) => t.status === "verified"],
  ["all", "All", () => true],
];

const TYPE_HELP: Record<string, string> = {
  ward_inspection: "Verified automatically when the assigned person is identified in the ward for the minimum time.",
  equipment_check: "Counts only time spent inside the equipment zone. Verified automatically when the time is met.",
  medication_delivery: "Bedside presence is collected as evidence only. A supervisor must confirm clinical completion.",
};

export default function Tasks() {
  const { can } = useAuth();
  const tasks = useData<Task[]>("/tasks");
  const [filter, setFilter] = useState("open");
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  useLiveRefresh(["task."], tasks.reload, 800);
  const fn = FILTERS.find((f) => f[0] === filter)![2];
  const list = (tasks.data ?? []).filter(fn);
  const counts = useMemo(() => Object.fromEntries(FILTERS.map(([k, , f]) => [k, (tasks.data ?? []).filter(f).length])), [tasks.data]);

  return (
    <>
      <PageHeader title="Tasks" subtitle="Assignments are verified from observed evidence. Presence alone never completes clinical work."
        actions={can("admin", "supervisor") && <Button icon={<Plus size={16} />} onClick={() => setCreating(true)}>Assign task</Button>} />
      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map(([k, label]) => (
          <button key={k} onClick={() => setFilter(k)} className={clsx("rounded-xl px-3.5 py-2 text-sm font-medium transition",
            filter === k ? "bg-white text-ink shadow-glass" : "text-ink-soft hover:bg-white/60")}>
            {label} <span className="ml-1 text-ink-faint num">{counts[k] ?? 0}</span>
          </button>
        ))}
      </div>
      {tasks.error && <ErrorNote message={tasks.error} onRetry={tasks.reload} />}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {tasks.loading && [0, 1, 2].map((i) => <Skeleton key={i} className="h-36" />)}
        {!tasks.loading && list.length === 0 && (
          <Panel className="md:col-span-2 xl:col-span-3"><Empty icon={<ClipboardCheck size={20} />} title="No tasks in this view" body={can("supervisor", "admin") ? "Assign an inspection, equipment check or medication round." : undefined} /></Panel>
        )}
        {list.map((t) => (
          <button key={t.id} onClick={() => setOpenId(t.id)} className="glass p-4 text-left transition hover:-translate-y-0.5 hover:shadow-lift">
            <div className="flex items-start justify-between gap-2">
              <p className="font-semibold leading-snug">{t.title}</p>
              <StatusBadge status={t.status} />
            </div>
            <p className="mt-1 text-[13px] text-ink-faint">{TASK_LABEL[t.task_type]}, {t.ward_name}{t.zone ? `, ${t.zone} zone` : ""}</p>
            <p className="mt-0.5 text-[13px] text-ink-soft">{t.staff_name} ({t.staff_code})</p>
            <div className="mt-3"><Progress value={t.progress} tone={t.status === "review_required" ? "amber" : t.status === "verified" ? "mint" : "teal"} /></div>
            <div className="mt-1.5 flex justify-between text-xs text-ink-faint num">
              <span>{Math.round(t.accumulated_seconds)} of {t.min_duration_sec}s observed</span>
              <span>{t.due_at ? `Due ${dateTime(t.due_at)}` : "No deadline"}</span>
            </div>
          </button>
        ))}
      </div>
      <CreateTask open={creating} onClose={() => setCreating(false)} onSaved={tasks.reload} />
      <TaskDetail id={openId} onClose={() => setOpenId(null)} onChanged={tasks.reload} />
    </>
  );
}

function CreateTask({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const staff = useData<Staff[]>(open ? "/staff" : null, [open]);
  const wards = useData<Ward[]>(open ? "/wards" : null, [open]);
  const blank = { title: "", task_type: "ward_inspection", staff_id: 0, ward_id: 0, min_duration_sec: 30, requires_confirmation: false, due_in_min: 60, zone: "", required_role: "" };
  const [f, setF] = useState(blank);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setF(blank); setErr(null); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (staff.data?.length && !f.staff_id) setF((x) => ({ ...x, staff_id: staff.data!.find((s) => s.active)?.id ?? 0 }));
    if (wards.data?.length && !f.ward_id) setF((x) => ({ ...x, ward_id: wards.data![0].id }));
  }, [staff.data, wards.data, f.staff_id, f.ward_id]);

  const pickType = (t: string) => {
    const preset = { ward_inspection: [30, false, ""], equipment_check: [20, false, "equipment"], medication_delivery: [30, true, "bedside"] }[t] as [number, boolean, string];
    setF({ ...f, task_type: t, min_duration_sec: preset[0], requires_confirmation: preset[1], zone: preset[2] });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      const due = f.due_in_min > 0 ? new Date(Date.now() + f.due_in_min * 60000).toISOString() : null;
      await api("/tasks", { method: "POST", json: { title: f.title, task_type: f.task_type, staff_id: f.staff_id, ward_id: f.ward_id,
        min_duration_sec: f.min_duration_sec, requires_confirmation: f.requires_confirmation, due_at: due, zone: f.zone, required_role: f.required_role || null } });
      toast({ tone: "ok", title: "Task assigned" }); onSaved(); onClose();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title="Assign task" wide>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-3">
          {Object.entries(TASK_LABEL).map(([k, v]) => (
            <button type="button" key={k} onClick={() => pickType(k)}
              className={clsx("rounded-2xl border p-3 text-left transition", f.task_type === k ? "border-teal bg-teal-tint/70" : "border-ink/10 bg-white/60 hover:bg-white")}>
              <p className="text-sm font-semibold">{v}</p>
              <p className="mt-1 text-xs leading-snug text-ink-soft">{TYPE_HELP[k]}</p>
            </button>
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Title"><input className="field" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="ICU evening inspection" required /></Field>
          <Field label="Assigned to">
            <select className="field" value={f.staff_id} onChange={(e) => setF({ ...f, staff_id: Number(e.target.value) })}>
              {staff.data?.filter((s) => s.active).map((s) => <option key={s.id} value={s.id}>{s.name} ({ROLE_LABEL[s.role]})</option>)}
            </select>
          </Field>
          <Field label="Ward">
            <select className="field" value={f.ward_id} onChange={(e) => setF({ ...f, ward_id: Number(e.target.value) })}>
              {wards.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </Field>
          <Field label="Zone" hint="Leave empty to count time anywhere in the ward.">
            <input className="field" value={f.zone} onChange={(e) => setF({ ...f, zone: e.target.value })} placeholder="bedside" />
          </Field>
          <Field label="Minimum observed time (seconds)"><input className="field num" type="number" min={5} max={7200} value={f.min_duration_sec} onChange={(e) => setF({ ...f, min_duration_sec: Number(e.target.value) })} /></Field>
          <Field label="Due in (minutes, 0 for no deadline)"><input className="field num" type="number" min={0} value={f.due_in_min} onChange={(e) => setF({ ...f, due_in_min: Number(e.target.value) })} /></Field>
          <Field label="Required role">
            <select className="field" value={f.required_role} onChange={(e) => setF({ ...f, required_role: e.target.value })}>
              <option value="">Any role</option>
              {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
          <div className="flex items-end pb-2"><Toggle checked={f.requires_confirmation} onChange={(v) => setF({ ...f, requires_confirmation: v })} label="Require supervisor confirmation" /></div>
        </div>
        {err && <ErrorNote message={err} />}
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button type="submit" busy={busy}>Assign task</Button></div>
      </form>
    </Modal>
  );
}

function TaskDetail({ id, onClose, onChanged }: { id: number | null; onClose: () => void; onChanged: () => void }) {
  const { can } = useAuth();
  const toast = useToast();
  const t = useData<Task>(id ? `/tasks/${id}` : null, [id]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useLiveRefresh(["task."], t.reload, 800);
  useEffect(() => { setNote(""); setErr(null); }, [id]);

  const review = async (decision: "approve" | "reject") => {
    setBusy(decision); setErr(null);
    try {
      await api(`/tasks/${id}/review`, { method: "POST", json: { decision, note } });
      toast({ tone: "ok", title: decision === "approve" ? "Task verified" : "Task rejected" });
      t.reload(); onChanged();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(null); }
  };
  const d = t.data;
  return (
    <Modal open={!!id} onClose={onClose} title={d?.title ?? "Task"} wide>
      {!d ? <Skeleton className="h-40" /> : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={d.status} />
            <Badge tone="sky">{TASK_LABEL[d.task_type]}</Badge>
            {d.requires_confirmation && <Badge tone="amber">Needs authorized confirmation</Badge>}
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <div><p className="text-ink-faint">Assigned to</p><p className="font-semibold">{d.staff_name}</p></div>
            <div><p className="text-ink-faint">Where</p><p className="font-semibold">{d.ward_name}{d.zone ? `, ${d.zone} zone` : ""}</p></div>
            <div><p className="text-ink-faint">Due</p><p className="font-semibold">{d.due_at ? dateTime(d.due_at) : "No deadline"}</p></div>
          </div>
          <div>
            <div className="mb-1.5 flex justify-between text-sm"><span className="font-medium">Observed evidence</span><span className="text-ink-faint num">{Math.round(d.accumulated_seconds)} / {d.min_duration_sec}s</span></div>
            <Progress value={d.progress} tone={d.status === "verified" ? "mint" : "teal"} />
          </div>
          <div>
            <p className="mb-2 text-sm font-medium">Evidence log</p>
            <ol className="relative space-y-3 border-l-2 border-teal/20 pl-4">
              {(d.evidence ?? []).length === 0 && <li className="text-sm text-ink-faint">No evidence observed yet.</li>}
              {d.evidence?.map((e) => (
                <li key={e.id} className="relative">
                  <span className="absolute -left-[22px] top-1 h-2.5 w-2.5 rounded-full bg-teal ring-4 ring-white" />
                  <p className="text-sm font-semibold">{pretty(e.evidence_type)}</p>
                  <p className="text-[13px] text-ink-soft">{e.detail}</p>
                  <p className="text-xs text-ink-faint">{time(e.observed_at)}</p>
                </li>
              ))}
            </ol>
          </div>
          {can("admin", "supervisor") && !["verified", "rejected"].includes(d.status) && (
            <div className="rounded-2xl bg-ink/[0.03] p-4">
              <p className="mb-2 text-sm font-medium">Supervisor review</p>
              <textarea className="field min-h-[72px]" value={note} onChange={(e) => setNote(e.target.value)} placeholder="What did you confirm? e.g. medication chart signed for bed 2" />
              {err && <div className="mt-2"><ErrorNote message={err} /></div>}
              <div className="mt-3 flex justify-end gap-2">
                <Button variant="soft" icon={<XCircle size={15} />} busy={busy === "reject"} disabled={note.trim().length < 3} onClick={() => review("reject")}>Reject</Button>
                <Button icon={<CheckCircle2 size={15} />} busy={busy === "approve"} disabled={note.trim().length < 3 || d.accumulated_seconds < d.min_duration_sec} onClick={() => review("approve")}>Confirm completion</Button>
              </div>
              {d.accumulated_seconds < d.min_duration_sec && <p className="mt-2 text-xs text-ink-faint">Confirmation unlocks once the required visual evidence has been observed.</p>}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
