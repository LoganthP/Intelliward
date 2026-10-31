import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { BellOff, Download } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Empty, ErrorNote, Modal, Panel, Skeleton, StatusBadge, severityTone, useToast } from "../components/ui";
import { api, download } from "../lib/api";
import { ALERT_LABEL, ago, dateTime } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useData } from "../lib/useData";
import type { Alert } from "../lib/types";

export default function Alerts() {
  const toast = useToast();
  const [tab, setTab] = useState<"active" | "resolved" | "dismissed">("active");
  const alerts = useData<Alert[]>(`/alerts?status=${tab}`, [tab]);
  const [closing, setClosing] = useState<{ alert: Alert; status: "resolved" | "dismissed" } | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  useLiveRefresh(["alert."], alerts.reload, 700);

  const update = async (a: Alert, status: string, n = "") => {
    setBusy(true);
    try {
      await api(`/alerts/${a.id}`, { method: "PATCH", json: { status, note: n } });
      toast({ tone: "ok", title: status === "acknowledged" ? "Alert acknowledged" : status === "resolved" ? "Alert resolved" : "Alert dismissed" });
      setClosing(null); setNote(""); alerts.reload();
    } catch (e) { toast({ tone: "warn", title: "Alert not updated", body: (e as Error).message }); }
    finally { setBusy(false); }
  };

  return (
    <>
      <PageHeader title="Alerts" subtitle="Each alert keeps its evidence and a recorded history of who handled it and why."
        actions={<Button variant="soft" icon={<Download size={16} />} onClick={() => download("/reports/alerts.csv", "alerts.csv")}>Export CSV</Button>} />
      <div className="mb-4 flex gap-2">
        {(["active", "resolved", "dismissed"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={clsx("rounded-xl px-3.5 py-2 text-sm font-medium", tab === t ? "bg-white shadow-glass" : "text-ink-soft hover:bg-white/60")}>
            {t === "active" ? "Needs attention" : t === "resolved" ? "Resolved" : "Dismissed"}
          </button>
        ))}
      </div>
      {alerts.error && <ErrorNote message={alerts.error} onRetry={alerts.reload} />}
      <div className="space-y-3">
        {alerts.loading && <Skeleton className="h-24" />}
        {!alerts.loading && alerts.data?.length === 0 && <Panel><Empty icon={<BellOff size={20} />} title={tab === "active" ? "No alerts need attention" : "Nothing here yet"} /></Panel>}
        <AnimatePresence initial={false}>
          {alerts.data?.map((a) => (
            <motion.div key={a.id} layout initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: 30 }}
              className={clsx("glass flex flex-wrap items-start gap-4 p-4", a.status === "open" && a.severity !== "low" && "border-l-4 border-l-coral")}>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">{ALERT_LABEL[a.alert_type] ?? a.alert_type}</p>
                  <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
                  <StatusBadge status={a.status} />
                </div>
                <p className="mt-1 text-sm text-ink-soft">{a.message}</p>
                <p className="mt-1 text-xs text-ink-faint">{a.ward_name ?? "Hospital"}{a.track_key ? `, track ${a.track_key}` : ""}, {dateTime(a.created_at)} ({ago(a.created_at)})</p>
                {a.history.length > 1 && (
                  <ul className="mt-2 space-y-0.5 text-xs text-ink-faint">
                    {a.history.slice(1).map((h, i) => <li key={i}>{h.status} by {h.by} {ago(h.at)}{h.note ? `: ${h.note}` : ""}</li>)}
                  </ul>
                )}
              </div>
              {tab === "active" && (
                <div className="flex flex-wrap gap-2">
                  {a.status === "open" && <Button size="sm" variant="soft" busy={busy} onClick={() => update(a, "acknowledged")}>Acknowledge</Button>}
                  <Button size="sm" onClick={() => setClosing({ alert: a, status: "resolved" })}>Resolve</Button>
                  <Button size="sm" variant="ghost" onClick={() => setClosing({ alert: a, status: "dismissed" })}>Dismiss</Button>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      <Modal open={!!closing} onClose={() => setClosing(null)} title={closing?.status === "resolved" ? "Resolve alert" : "Dismiss alert"}>
        <p className="mb-2 text-sm text-ink-soft">{closing?.alert.message}</p>
        <textarea className="field min-h-[90px]" value={note} onChange={(e) => setNote(e.target.value)} placeholder={closing?.status === "resolved" ? "What was done?" : "Why is this not an issue? e.g. authorized visitor"} />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setClosing(null)}>Cancel</Button>
          <Button busy={busy} disabled={note.trim().length < 3} onClick={() => closing && update(closing.alert, closing.status, note)}>{closing?.status === "resolved" ? "Resolve alert" : "Dismiss alert"}</Button>
        </div>
      </Modal>
    </>
  );
}
