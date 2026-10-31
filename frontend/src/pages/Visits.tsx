import { Download, Footprints } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Empty, ErrorNote, Panel, Skeleton, StatusBadge, Table, useToast } from "../components/ui";
import { download } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ROLE_LABEL, dateTime, duration, time } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useData } from "../lib/useData";
import type { Visit, Ward } from "../lib/types";

export default function Visits() {
  const { can } = useAuth();
  const toast = useToast();
  const [ward, setWard] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const wards = useData<Ward[]>("/wards");
  const params = new URLSearchParams();
  if (ward) params.set("ward_id", ward);
  if (status) params.set("status", status);
  const visits = useData<Visit[]>(`/visits?${params.toString()}`, [ward, status]);
  useLiveRefresh(["visit."], visits.reload, 1500);
  const rows = (visits.data ?? []).filter((v) => !q || `${v.staff_name} ${v.staff_code}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <>
      <PageHeader title={can("staff") ? "My visits" : "Visits"} subtitle="Consolidated ward presence. Short disappearances within the merge window stay part of the same visit."
        actions={can("admin", "supervisor") && <Button variant="soft" icon={<Download size={16} />} onClick={() => download("/reports/visits.csv", "visits.csv").catch((e) => toast({ tone: "warn", title: e.message }))}>Export CSV</Button>} />
      <div className="mb-4 flex flex-wrap gap-2">
        {can("admin", "supervisor") && <input className="field w-56" placeholder="Search staff" value={q} onChange={(e) => setQ(e.target.value)} />}
        <select className="field w-48" value={ward} onChange={(e) => setWard(e.target.value)}>
          <option value="">All wards</option>
          {wards.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
        <select className="field w-40" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option><option value="active">In ward</option><option value="exited">Left</option>
        </select>
      </div>
      {visits.error && <ErrorNote message={visits.error} onRetry={visits.reload} />}
      <Panel>
        {visits.loading ? <div className="p-5"><Skeleton className="h-48" /></div> : (
          <Table head={["Staff", "Ward", "Entry", "Exit", "Duration", "Segments", "Status"]}
            empty={rows.length === 0 && <Empty icon={<Footprints size={20} />} title="No visits in the last 7 days" body="Visits are created when an enrolled person is verified on a camera." />}>
            {rows.map((v) => (
              <tr key={v.id} className="hover:bg-white/40">
                <td className="px-5 py-3"><p className="font-semibold">{v.staff_name}</p><p className="text-xs text-ink-faint">{v.staff_code}, {ROLE_LABEL[v.role] ?? v.role}</p></td>
                <td className="px-5 py-3">{v.ward_name}</td>
                <td className="px-5 py-3 num">{dateTime(v.entry_at)}</td>
                <td className="px-5 py-3 num">{v.exit_at ? time(v.exit_at) : "—"}</td>
                <td className="px-5 py-3 font-semibold num">{duration(v.duration_seconds)}</td>
                <td className="px-5 py-3">{v.fragments > 1 ? <Badge tone="sky">{v.fragments} merged</Badge> : <span className="text-ink-faint">1</span>}</td>
                <td className="px-5 py-3"><StatusBadge status={v.status} /></td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
    </>
  );
}
