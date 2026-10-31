import { Download } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageHeader } from "../components/Shell";
import { Button, ErrorNote, Panel, PanelHead, Skeleton } from "../components/ui";
import { download } from "../lib/api";
import { ALERT_LABEL, pretty } from "../lib/format";
import { useData } from "../lib/useData";

interface Trends {
  alerts_by_day: { day: string; low: number; medium: number; high: number; critical: number }[];
  alerts_by_type: { type: string; count: number }[];
  tasks_by_status: { status: string; count: number }[];
  presence_by_staff: { code: string; name: string; minutes: number }[];
  minutes_by_ward: { ward: string; minutes: number }[];
}
const PALETTE = ["#0B7A83", "#2EC4A0", "#5AA9F0", "#D98714", "#E5484D", "#8B7CF6", "#7F98AD"];
const tip = { contentStyle: { borderRadius: 12, border: "1px solid rgba(255,255,255,.8)", boxShadow: "0 10px 30px -12px rgba(15,46,68,.3)" } };
const axis = { tick: { fontSize: 11, fill: "#7F98AD" }, axisLine: false, tickLine: false };

export default function Analytics() {
  const [days, setDays] = useState(7);
  const t = useData<Trends>(`/analytics/trends?days=${days}`, [days]);
  const d = t.data;
  return (
    <>
      <PageHeader title="Analytics" subtitle="Operational patterns for review. Not a measure of individual performance."
        actions={<>
          <select className="field w-36" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={1}>Last 24 hours</option><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option>
          </select>
          {["visits", "tasks", "alerts", "audit"].map((k) => (
            <Button key={k} variant="soft" size="md" icon={<Download size={15} />} onClick={() => download(`/reports/${k}.csv`, `${k}.csv`)}>{pretty(k)}</Button>
          ))}
        </>} />
      {t.error && <ErrorNote message={t.error} onRetry={t.reload} />}
      {!d ? <Skeleton className="h-96" /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel>
            <PanelHead title="Alerts by day and severity" />
            <div className="h-72 p-3"><ResponsiveContainer>
              <BarChart data={d.alerts_by_day.map((x) => ({ ...x, day: x.day.slice(5) }))}>
                <CartesianGrid vertical={false} stroke="rgba(15,46,68,.06)" />
                <XAxis dataKey="day" {...axis} /><YAxis allowDecimals={false} {...axis} width={30} />
                <Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="low" stackId="a" fill="#5AA9F0" radius={[0, 0, 0, 0]} />
                <Bar dataKey="medium" stackId="a" fill="#D98714" />
                <Bar dataKey="high" stackId="a" fill="#E5484D" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer></div>
          </Panel>
          <Panel>
            <PanelHead title="Task outcomes" hint="Tasks created in the selected period" />
            <div className="h-72 p-3"><ResponsiveContainer>
              <PieChart>
                <Pie data={d.tasks_by_status.map((x) => ({ name: pretty(x.status), value: x.count }))} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={3}>
                  {d.tasks_by_status.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Pie>
                <Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer></div>
          </Panel>
          <Panel>
            <PanelHead title="Time in wards by staff (minutes)" />
            <div className="h-72 p-3"><ResponsiveContainer>
              <BarChart data={d.presence_by_staff} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" {...axis} /><YAxis type="category" dataKey="name" width={120} {...axis} />
                <Tooltip {...tip} /><Bar dataKey="minutes" fill="#0B7A83" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer></div>
          </Panel>
          <Panel>
            <PanelHead title="Alert types" />
            <div className="h-72 p-3"><ResponsiveContainer>
              <BarChart data={d.alerts_by_type.map((x) => ({ ...x, label: ALERT_LABEL[x.type] ?? x.type }))}>
                <CartesianGrid vertical={false} stroke="rgba(15,46,68,.06)" />
                <XAxis dataKey="label" {...axis} interval={0} /><YAxis allowDecimals={false} {...axis} width={30} />
                <Tooltip {...tip} /><Bar dataKey="count" fill="#2EC4A0" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer></div>
          </Panel>
        </div>
      )}
    </>
  );
}
