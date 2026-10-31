export const ROLE_LABEL: Record<string, string> = { nurse: "Nurse", doctor: "Doctor", ot_staff: "OT staff", cleaner: "Cleaner" };
export const TASK_LABEL: Record<string, string> = {
  ward_inspection: "Ward inspection", equipment_check: "Equipment check", medication_delivery: "Medication delivery",
};
export const STATUS_LABEL: Record<string, string> = {
  pending: "Pending", in_progress: "In progress", evidence_collected: "Evidence collected", verified: "Verified",
  review_required: "Needs review", overdue: "Overdue", rejected: "Rejected", open: "Open", acknowledged: "Acknowledged",
  resolved: "Resolved", dismissed: "Dismissed", active: "In ward", exited: "Left", online: "Live", offline: "Offline",
  stopped: "Stopped", starting: "Starting",
};
export const ALERT_LABEL: Record<string, string> = {
  unknown_person: "Unrecognized person", unauthorized_access: "Unauthorized entry", role_mismatch: "Uniform mismatch",
  prolonged_stay: "Prolonged stay", task_overdue: "Task overdue", camera_offline: "Camera offline",
};

export const toDate = (iso: string | null | undefined) => (iso ? new Date(iso) : null);

export function time(iso: string | null | undefined) {
  const d = toDate(iso);
  return d ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";
}
export function dateTime(iso: string | null | undefined) {
  const d = toDate(iso);
  return d ? d.toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
}
export function duration(sec: number) {
  if (!sec || sec < 0) return "0s";
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${s.toString().padStart(2, "0")}s`;
  return `${s}s`;
}
export function ago(iso: string | null | undefined) {
  const d = toDate(iso);
  if (!d) return "never";
  const s = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
  if (s < 10) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
export const pretty = (s: string | null | undefined) => (s ? (STATUS_LABEL[s] ?? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())) : "—");
