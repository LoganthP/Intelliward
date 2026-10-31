export type AccessRole = "admin" | "supervisor" | "staff";
export interface User { id: number; username: string; full_name: string; access_role: AccessRole; staff_id: number | null; active: boolean }
export interface Staff {
  id: number; staff_code: string; name: string; role: string; department: string; active: boolean;
  consent_recorded: boolean; created_at: string; enrollment_images: number; embedding_models: string[];
  enrolled: boolean; ward_ids: number[];
}
export interface Ward { id: number; code: string; name: string; location: string; restricted: boolean; prolonged_stay_minutes: number }
export interface Zone { name: string; x1: number; y1: number; x2: number; y2: number }
export interface Camera {
  id: number; code: string; name: string; ward_id: number; ward_name: string | null; source: string; enabled: boolean;
  status: "stopped" | "starting" | "online" | "offline"; last_frame_at: string | null; fps: number; zones: Zone[]; error?: string;
}
export interface Visit {
  id: number; staff_id: number; staff_name: string; staff_code: string; role: string; ward_id: number; ward_name: string;
  camera_id: number | null; entry_at: string; last_seen: string; exit_at: string | null; status: string;
  duration_seconds: number; fragments: number; track_keys: string[];
}
export interface Evidence { id: number; evidence_type: string; detail: string; observed_at: string; verification_state: string }
export interface Task {
  id: number; title: string; task_type: string; staff_id: number; staff_name: string; staff_code: string; ward_id: number;
  ward_name: string; zone: string | null; required_role: string | null; min_duration_sec: number; requires_confirmation: boolean;
  due_at: string | null; status: string; accumulated_seconds: number; progress: number; created_at: string;
  completed_at: string | null; notes: string; evidence?: Evidence[];
}
export interface Alert {
  id: number; alert_type: string; severity: "low" | "medium" | "high" | "critical"; ward_id: number | null;
  ward_name: string | null; camera_id: number | null; staff_id: number | null; staff_name: string | null;
  track_key: string | null; message: string; evidence: Record<string, unknown>; status: string; created_at: string;
  updated_at: string; history: { at: string; status: string; by: string; note?: string }[];
}
export interface LiveTrack {
  track_id: string; bbox: number[] | null; identity_status: "verified" | "unknown" | "pending"; staff_id: number | null;
  staff_code: string | null; staff_name: string | null; role: string | null; role_color: string | null;
  similarity: number; zone: string | null;
}
export interface AuditEvent { sequence: number; event_id: string; event_type: string; occurred_at: string; payload: string; prev_hash: string; curr_hash: string; anchored: boolean }
export interface VerifyReport {
  ok: boolean; events_checked: number; batches_checked: number; anchors_checked: number; head_hash: string;
  last_anchored_sequence: number; last_verified_anchored_sequence: number; unanchored_events: number;
  issues: { code: string; message: string; sequence: number | null }[]; verified_at?: string;
}
export type Settings = Record<string, unknown> & { role_color_map: Record<string, string> };
