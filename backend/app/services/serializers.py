from app.core.timeutil import iso, utcnow
from app.db import models as m


def staff(s: m.Staff, model_versions: list[str] | None = None) -> dict:
    return {
        "id": s.id, "staff_code": s.staff_code, "name": s.name, "role": s.role, "department": s.department,
        "active": s.active, "consent_recorded": s.consent_recorded, "created_at": iso(s.created_at),
        "enrollment_images": len(s.images),
        "embedding_models": [e.model_version for e in s.embeddings],
        "enrolled": len(s.embeddings) > 0,
        "ward_ids": [a.ward_id for a in s.access],
    }


def ward(w: m.Ward) -> dict:
    return {"id": w.id, "code": w.code, "name": w.name, "location": w.location, "restricted": w.restricted,
            "prolonged_stay_minutes": w.prolonged_stay_minutes}


def camera(c: m.Camera) -> dict:
    return {"id": c.id, "code": c.code, "name": c.name, "ward_id": c.ward_id,
            "ward_name": c.ward.name if c.ward else None, "source": c.source, "enabled": c.enabled,
            "status": c.status, "last_frame_at": iso(c.last_frame_at), "fps": round(c.fps or 0, 1),
            "zones": c.zones or []}


def visit(v: m.Visit) -> dict:
    end = v.exit_at or v.last_seen or utcnow()
    return {"id": v.id, "staff_id": v.staff_id, "staff_name": v.staff.name if v.staff else None,
            "staff_code": v.staff.staff_code if v.staff else None, "role": v.staff.role if v.staff else None,
            "ward_id": v.ward_id, "ward_name": v.ward.name if v.ward else None, "camera_id": v.camera_id,
            "entry_at": iso(v.entry_at), "last_seen": iso(v.last_seen), "exit_at": iso(v.exit_at),
            "status": v.status, "duration_seconds": max(0, int((end - v.entry_at).total_seconds())),
            "fragments": v.fragments, "track_keys": v.track_keys or []}


def task(t: m.Task, with_evidence: bool = False) -> dict:
    d = {"id": t.id, "title": t.title, "task_type": t.task_type, "staff_id": t.staff_id,
         "staff_name": t.staff.name if t.staff else None, "staff_code": t.staff.staff_code if t.staff else None,
         "ward_id": t.ward_id, "ward_name": t.ward.name if t.ward else None, "zone": t.zone,
         "required_role": t.required_role, "min_duration_sec": t.min_duration_sec,
         "requires_confirmation": t.requires_confirmation, "due_at": iso(t.due_at), "status": t.status,
         "accumulated_seconds": round(t.accumulated_seconds, 1),
         "progress": min(1.0, (t.accumulated_seconds / t.min_duration_sec) if t.min_duration_sec else 1.0),
         "created_at": iso(t.created_at), "completed_at": iso(t.completed_at), "notes": t.notes}
    if with_evidence:
        d["evidence"] = [{"id": e.id, "evidence_type": e.evidence_type, "detail": e.detail,
                          "observed_at": iso(e.observed_at), "verification_state": e.verification_state}
                         for e in t.evidence]
    return d


def alert(a: m.Alert, names: dict | None = None) -> dict:
    names = names or {}
    return {"id": a.id, "alert_type": a.alert_type, "severity": a.severity, "ward_id": a.ward_id,
            "ward_name": names.get(("ward", a.ward_id)), "camera_id": a.camera_id, "staff_id": a.staff_id,
            "staff_name": names.get(("staff", a.staff_id)), "track_key": a.track_key, "message": a.message,
            "evidence": a.evidence or {}, "status": a.status, "created_at": iso(a.created_at),
            "updated_at": iso(a.updated_at), "history": a.history or []}


def user(u: m.User) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "access_role": u.access_role,
            "staff_id": u.staff_id, "active": u.active}
