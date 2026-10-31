import clsx from "clsx";
import { motion } from "framer-motion";
import { Anchor, FlaskConical, Link2, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Empty, ErrorNote, Modal, Panel, PanelHead, Skeleton, Table, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime, pretty } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useData } from "../lib/useData";
import type { AuditEvent, VerifyReport } from "../lib/types";

interface Sim { events: number; batches: number; results: { attack: string; description: string; detected_with_anchors: boolean; detected_chain_only: boolean; first_issue: { code: string; message: string } | null }[] }
interface Batches { database: { id: number; first_sequence: number; last_sequence: number; merkle_root: string; external_reference: string; created_at: string }[]; external: { batch_id: number; anchored_at: string; anchor_hash: string }[] }
const short = (h: string) => `${h.slice(0, 10)}…${h.slice(-6)}`;

export default function Audit() {
  const { can } = useAuth();
  const toast = useToast();
  const events = useData<AuditEvent[]>("/audit/events?limit=60");
  const batches = useData<Batches>("/audit/batches");
  const [report, setReport] = useState<VerifyReport | null>(null);
  const [sim, setSim] = useState<Sim | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [viewing, setViewing] = useState<AuditEvent | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useLiveRefresh(["visit.", "task.", "alert.", "staff.", "camera."], events.reload, 3000);

  const run = async (kind: "verify" | "anchor" | "sim") => {
    setBusy(kind); setErr(null);
    try {
      if (kind === "verify") setReport(await api<VerifyReport>("/audit/verify", { method: "POST" }));
      if (kind === "anchor") {
        const r = await api<{ anchored: boolean; message?: string; first_sequence?: number; last_sequence?: number }>("/audit/anchor", { method: "POST" });
        toast({ tone: "ok", title: r.anchored ? `Anchored events ${r.first_sequence}–${r.last_sequence}` : r.message ?? "Nothing to anchor" });
      }
      if (kind === "sim") setSim(await api<Sim>("/audit/simulate-tamper", { method: "POST" }));
      events.reload(); batches.reload();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };

  return (
    <>
      <PageHeader title="Audit integrity" subtitle="Every event is SHA-256 chained to the one before it. Merkle batches are anchored to a separate append-only store, so edits, deletions and full rewrites become detectable."
        actions={<>
          <Button variant="soft" icon={<Anchor size={16} />} busy={busy === "anchor"} onClick={() => run("anchor")}>Anchor now</Button>
          <Button icon={<ShieldCheck size={16} />} busy={busy === "verify"} onClick={() => run("verify")}>Verify integrity</Button>
        </>} />
      {err && <div className="mb-4"><ErrorNote message={err} /></div>}

      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <Panel strong className="overflow-hidden">
          {!report ? (
            <Empty icon={<ShieldCheck size={20} />} title="Integrity not checked in this session" body="Verification recomputes every hash, every Merkle root and compares them with the independent anchors." action={<Button busy={busy === "verify"} onClick={() => run("verify")}>Verify integrity</Button>} />
          ) : (
            <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="p-5">
              <div className="flex items-center gap-4">
                <div className={clsx("grid h-14 w-14 place-items-center rounded-2xl", report.ok ? "bg-mint-tint text-[#137a62]" : "bg-coral-tint text-coral")}>
                  {report.ok ? <ShieldCheck size={28} /> : <ShieldAlert size={28} />}
                </div>
                <div>
                  <p className="font-display text-xl font-semibold">{report.ok ? "Audit trail intact" : "Integrity failure detected"}</p>
                  <p className="text-sm text-ink-soft">{report.events_checked} events, {report.batches_checked} batches, {report.anchors_checked} external anchors checked</p>
                </div>
              </div>
              <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl bg-white/60 p-3"><dt className="text-ink-faint">Verified up to anchored event</dt><dd className="font-semibold num">{report.last_verified_anchored_sequence}</dd></div>
                <div className="rounded-xl bg-white/60 p-3"><dt className="text-ink-faint">Not yet anchored</dt><dd className="font-semibold num">{report.unanchored_events} events</dd></div>
                <div className="col-span-2 rounded-xl bg-white/60 p-3"><dt className="text-ink-faint">Chain head</dt><dd className="break-all font-mono text-xs">{report.head_hash}</dd></div>
              </dl>
              {!report.ok && (
                <ul className="mt-4 space-y-1.5">
                  {report.issues.map((i, k) => <li key={k} className="rounded-xl bg-coral-tint/70 px-3 py-2 text-sm text-[#9b2328]"><b>{i.code}</b>{i.sequence ? ` at #${i.sequence}` : ""}: {i.message}</li>)}
                </ul>
              )}
              {!report.ok && <p className="mt-3 text-xs text-ink-faint">The damaged history is left untouched for investigation. Nothing is repaired automatically.</p>}
            </motion.div>
          )}
        </Panel>

        <Panel>
          <PanelHead title="Tamper detection test" hint="Applies six attacks to an in-memory copy of the log. The real log is never modified."
            action={can("admin") && <Button size="sm" variant="soft" icon={<FlaskConical size={14} />} busy={busy === "sim"} onClick={() => run("sim")}>Run test</Button>} />
          <div className="p-3">
            {!sim ? <p className="px-2 pb-2 text-sm text-ink-faint">{can("admin") ? "Run the test to compare chain-only checking with external anchoring." : "Only administrators can run the test."}</p> : (
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[12.5px] text-ink-faint"><th className="px-2 py-1.5 font-medium">Attack</th><th className="px-2 font-medium">Chain only</th><th className="px-2 font-medium">With anchors</th></tr></thead>
                <tbody>
                  {sim.results.map((r) => (
                    <tr key={r.attack} className="border-t border-ink/5" title={r.description}>
                      <td className="px-2 py-2"><p className="font-semibold">{pretty(r.attack)}</p><p className="text-xs text-ink-faint">{r.description}</p></td>
                      <td className="px-2"><Badge tone={r.detected_chain_only ? "mint" : "coral"}>{r.detected_chain_only ? "Detected" : "Missed"}</Badge></td>
                      <td className="px-2"><Badge tone={r.detected_with_anchors ? "mint" : "coral"}>{r.detected_with_anchors ? "Detected" : "Missed"}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Panel>
      </div>

      <Panel className="mt-4">
        <PanelHead title="Recent audit events" hint="Newest first. Select an event to see the exact hashed record." />
        {events.loading ? <div className="p-5"><Skeleton className="h-40" /></div> : (
          <Table head={["#", "Event", "Time", "Previous hash", "Hash", "Anchor"]}
            empty={events.data?.length === 0 && <Empty title="No events yet" />}>
            {events.data?.map((e) => (
              <tr key={e.sequence} className="cursor-pointer hover:bg-white/50" onClick={() => setViewing(e)}>
                <td className="px-5 py-2.5 font-semibold num">{e.sequence}</td>
                <td className="px-5 py-2.5">{e.event_type}</td>
                <td className="px-5 py-2.5 num">{dateTime(e.occurred_at)}</td>
                <td className="px-5 py-2.5 font-mono text-xs text-ink-faint">{short(e.prev_hash)}</td>
                <td className="px-5 py-2.5 font-mono text-xs">{short(e.curr_hash)}</td>
                <td className="px-5 py-2.5">{e.anchored ? <Badge tone="mint"><Link2 size={11} /> Anchored</Badge> : <Badge>Pending</Badge>}</td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>

      <Panel className="mt-4">
        <PanelHead title="Anchored batches" hint="Stored in the database and, independently, in the append-only anchor file" />
        <div className="p-3">
          {!batches.data?.database.length ? <p className="px-2 pb-2 text-sm text-ink-faint">No batches yet. Events are anchored every 25 events or every minute.</p> : (
            <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {batches.data.database.slice(0, 9).map((b) => (
                <li key={b.id} className="rounded-xl bg-white/55 px-3 py-2 text-sm">
                  <p className="font-semibold">Batch {b.id}: events {b.first_sequence}–{b.last_sequence}</p>
                  <p className="font-mono text-xs text-ink-faint">root {short(b.merkle_root)}</p>
                  <p className="text-xs text-ink-faint">{b.external_reference}, {dateTime(b.created_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Panel>

      <Modal open={!!viewing} onClose={() => setViewing(null)} title={viewing ? `Event #${viewing.sequence}` : ""} wide>
        {viewing && (
          <div className="space-y-3 text-sm">
            <p className="text-ink-soft">hash = SHA-256(previous hash ‖ canonical record)</p>
            <pre className="max-h-80 overflow-auto rounded-xl bg-ink/[0.04] p-3 text-xs">{JSON.stringify(JSON.parse(viewing.payload), null, 2)}</pre>
            <p className="break-all font-mono text-xs"><span className="text-ink-faint">previous </span>{viewing.prev_hash}</p>
            <p className="break-all font-mono text-xs"><span className="text-ink-faint">hash </span>{viewing.curr_hash}</p>
          </div>
        )}
      </Modal>
    </>
  );
}
