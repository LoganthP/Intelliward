"""Visit lifecycle, identity/role fusion outcomes, task verification and alert rules.

All functions expect the caller to hold audit.write_lock and to commit afterwards.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.timeutil import iso, utcnow
from app.db.models import Camera, Staff, StaffWardAccess, Task, TaskEvidence, Track, Visit, Ward
from . import audit, serializers, settings_service
from .alerts import raise_alert
from .hub import hub

OPEN_TASK_STATES = ("pending", "in_progress", "overdue")
EVIDENCE_GAP_SECONDS = 4.0


def _zone_of(camera: Camera, bbox: list[float] | None) -> str | None:
    """Zone containing the person's foot point (bottom-centre of the normalized bbox)."""
    if not bbox or not camera.zones:
        return None
    x = (bbox[0] + bbox[2]) / 2
    y = bbox[3]
    for z in camera.zones:
        if z["x1"] <= x <= z["x2"] and z["y1"] <= y <= z["y2"]:
            return z["name"]
    return None


# ---------------------------------------------------------------- tracks
def upsert_track(db: Session, camera: Camera, obs: dict, now: datetime, cfg: dict) -> Track:
    key = str(obs["track_id"])
    tr = db.query(Track).filter(Track.camera_id == camera.id, Track.track_key == key).first()
    if tr is None:
        tr = Track(camera_id=camera.id, track_key=key, first_seen=now, last_seen=now, flags={})
        db.add(tr)
    tr.last_seen = now
    tr.active = True
    tr.role_color = obs.get("role_color") or tr.role_color
    status = obs.get("identity_status", "pending")
    staff_id = obs.get("staff_id")
    if status == "verified" and staff_id:
        if tr.identity_status != "verified" or tr.staff_id != staff_id:
            s = db.get(Staff, staff_id)
            if s is not None and s.active:
                tr.staff_id = staff_id
                tr.identity_status = "verified"
                tr.similarity = float(obs.get("similarity") or 0)
                audit.append(db, "identity.verified", {"camera": camera.code, "track": key, "staff_id": staff_id,
                                                       "staff_code": s.staff_code, "similarity": round(tr.similarity, 4),
                                                       "model": obs.get("model_version")})
    elif tr.identity_status != "verified":
        # A verified identity is never silently replaced by a weaker state on the same track.
        tr.identity_status = status
        tr.similarity = float(obs.get("similarity") or 0)
    db.flush()
    return tr


# ---------------------------------------------------------------- visits
def update_visit(db: Session, camera: Camera, tr: Track, staff: Staff, now: datetime, cfg: dict) -> Visit:
    ward_id = camera.ward_id
    v = (db.query(Visit).filter(Visit.staff_id == staff.id, Visit.ward_id == ward_id,
                                Visit.status.in_(("provisional", "active"))).order_by(Visit.id.desc()).first())
    if v is None:
        merge_after = now - timedelta(seconds=cfg["visit_merge_window_seconds"])
        recent = (db.query(Visit).filter(Visit.staff_id == staff.id, Visit.ward_id == ward_id,
                                         Visit.status == "exited", Visit.exit_at >= merge_after)
                  .order_by(Visit.exit_at.desc()).first())
        if recent is not None:
            recent.status = "active"
            recent.exit_at = None
            recent.fragments += 1
            recent.flags = {**(recent.flags or {}), "reopened": True}
            v = recent
            audit.append(db, "visit.reopened", {"visit_id": v.id, "staff_code": staff.staff_code,
                                                "ward_id": ward_id, "track": tr.track_key})
            hub.publish("visit.updated", serializers.visit(v), staff_scope=staff.id)
        else:
            v = Visit(staff_id=staff.id, ward_id=ward_id, camera_id=camera.id, entry_at=now, last_seen=now,
                      status="provisional", track_keys=[], flags={})
            db.add(v)
            db.flush()
    v.last_seen = now
    if tr.track_key not in (v.track_keys or []):
        v.track_keys = [*(v.track_keys or []), tr.track_key][-20:]
    if v.status == "provisional" and (now - v.entry_at).total_seconds() >= cfg["visit_confirm_seconds"]:
        v.status = "active"
        audit.append(db, "visit.started", {"visit_id": v.id, "staff_code": staff.staff_code,
                                           "ward_id": ward_id, "entry_at": iso(v.entry_at), "track": tr.track_key})
        hub.publish("visit.started", serializers.visit(v), staff_scope=staff.id)
        _check_authorization(db, camera, staff, v)
    db.flush()
    return v


def _check_authorization(db: Session, camera: Camera, staff: Staff, v: Visit):
    ward = db.get(Ward, camera.ward_id)
    if ward is None or not ward.restricted:
        return
    allowed = db.query(StaffWardAccess.id).filter(StaffWardAccess.staff_id == staff.id,
                                                  StaffWardAccess.ward_id == ward.id).first()
    if not allowed:
        raise_alert(db, "unauthorized_access", "high",
                    f"{staff.name} ({staff.staff_code}) entered restricted {ward.name} without authorization",
                    ward_id=ward.id, camera_id=camera.id, staff_id=staff.id,
                    evidence={"visit_id": v.id, "camera": camera.code}, dedup_key=f"unauth:visit:{v.id}")


# ---------------------------------------------------------------- role consistency
def check_role(db: Session, camera: Camera, tr: Track, staff: Staff, obs: dict, cfg: dict):
    color = obs.get("role_color")
    conf = float(obs.get("role_color_conf") or 0)
    expected = (cfg.get("role_color_map") or {}).get(staff.role)
    if not color or color == "unknown" or conf < 0.5 or not expected:
        return
    if color != expected:
        tr.mismatch_count += 1
    else:
        tr.mismatch_count = 0
    if tr.mismatch_count >= cfg["role_mismatch_observations"] and not (tr.flags or {}).get("mismatch_alerted"):
        tr.flags = {**(tr.flags or {}), "mismatch_alerted": True}
        raise_alert(db, "role_mismatch", "medium",
                    f"{staff.name} is registered as {staff.role.replace('_', ' ')} but the uniform cue reads "
                    f"{color} (expected {expected}). Review required; identity and role were not changed.",
                    ward_id=camera.ward_id, camera_id=camera.id, staff_id=staff.id, track_key=tr.track_key,
                    evidence={"observed_color": color, "expected_color": expected, "confidence": round(conf, 2)},
                    dedup_key=f"role:{camera.id}:{tr.track_key}")


# ---------------------------------------------------------------- tasks
def evaluate_tasks(db: Session, camera: Camera, staff: Staff, obs: dict, now: datetime):
    tasks = db.query(Task).filter(Task.staff_id == staff.id, Task.ward_id == camera.ward_id,
                                  Task.status.in_(OPEN_TASK_STATES)).all()
    if not tasks:
        return
    zone = _zone_of(camera, obs.get("bbox"))
    for t in tasks:
        if t.zone and t.zone != zone:
            t.last_evidence_at = None  # presence outside the required zone breaks the dwell interval
            continue
        if t.status == "pending":
            _set_status(db, t, "in_progress", "Assigned staff verified in the required location")
            db.add(TaskEvidence(task_id=t.id, evidence_type="presence_start", observed_at=now,
                                detail=f"Verified at {camera.code}" + (f", zone {zone}" if zone else "")))
        if t.last_evidence_at is not None:
            gap = (now - t.last_evidence_at).total_seconds()
            if 0 < gap <= EVIDENCE_GAP_SECONDS:
                t.accumulated_seconds += gap
        t.last_evidence_at = now
        if t.accumulated_seconds >= t.min_duration_sec:
            db.add(TaskEvidence(task_id=t.id, evidence_type="dwell_satisfied", observed_at=now,
                                detail=f"Observed {int(t.accumulated_seconds)}s of required {t.min_duration_sec}s"
                                       + (f" in zone {t.zone}" if t.zone else "")))
            if t.requires_confirmation:
                _set_status(db, t, "review_required",
                            "Visual evidence collected; authorized confirmation required for completion")
            else:
                t.completed_at = now
                _set_status(db, t, "verified", "All configured evidence conditions satisfied")
        hub.publish("task.progress", serializers.task(t), staff_scope=t.staff_id)


def _set_status(db: Session, t: Task, status: str, reason: str):
    old = t.status
    if old == status:
        return
    t.status = status
    db.flush()
    audit.append(db, "task.status_changed", {"task_id": t.id, "from": old, "to": status, "reason": reason,
                                             "accumulated_seconds": round(t.accumulated_seconds, 1)})
    hub.publish("task.updated", serializers.task(t), staff_scope=t.staff_id)


# ---------------------------------------------------------------- ingestion entry point
def process_observations(db: Session, payload: dict) -> dict:
    camera = db.query(Camera).filter(Camera.code == payload["camera_id"]).first()
    if camera is None:
        return {"accepted": 0, "error": "unknown camera"}
    cfg = settings_service.get_all(db)
    now = utcnow()
    camera.last_frame_at = now
    if camera.status != "online":
        camera.status = "online"
        hub.publish("camera.status", serializers.camera(camera))
    if payload.get("fps") is not None:
        camera.fps = float(payload["fps"])
    accepted = 0
    live = []
    for obs in payload.get("tracks", []):
        tr = upsert_track(db, camera, obs, now, cfg)
        accepted += 1
        staff = db.get(Staff, tr.staff_id) if tr.identity_status == "verified" and tr.staff_id else None
        if staff is not None:
            update_visit(db, camera, tr, staff, now, cfg)
            check_role(db, camera, tr, staff, obs, cfg)
            evaluate_tasks(db, camera, staff, obs, now)
        elif tr.identity_status == "unknown":
            age = (now - tr.first_seen).total_seconds()
            if age >= cfg["unknown_alert_seconds"] and not (tr.flags or {}).get("unknown_alerted"):
                tr.flags = {**(tr.flags or {}), "unknown_alerted": True}
                ward = db.get(Ward, camera.ward_id)
                raise_alert(db, "unknown_person", "high" if ward and ward.restricted else "medium",
                            f"Unrecognized person in {ward.name if ward else 'ward'} for {int(age)}s",
                            ward_id=camera.ward_id, camera_id=camera.id, track_key=tr.track_key,
                            evidence={"camera": camera.code, "best_similarity": round(tr.similarity, 3)},
                            dedup_key=f"unknown:{camera.id}:{tr.track_key}:{tr.first_seen.isoformat()}")
        live.append({"track_id": tr.track_key, "bbox": obs.get("bbox"), "identity_status": tr.identity_status,
                     "staff_id": staff.id if staff else None, "staff_code": staff.staff_code if staff else None,
                     "staff_name": staff.name if staff else None, "role": staff.role if staff else None,
                     "role_color": obs.get("role_color"), "similarity": round(tr.similarity, 3),
                     "zone": _zone_of(camera, obs.get("bbox"))})
    for key in payload.get("lost_tracks", []):
        tr = db.query(Track).filter(Track.camera_id == camera.id, Track.track_key == str(key)).first()
        if tr:
            tr.active = False
    hub.publish("monitoring.tracks", {"camera_id": camera.code, "ward_id": camera.ward_id, "at": iso(now),
                                      "tracks": live})
    return {"accepted": accepted}


# ---------------------------------------------------------------- periodic sweeps
def sweep(db: Session) -> None:
    cfg = settings_service.get_all(db)
    now = utcnow()
    timeout = timedelta(seconds=cfg["visit_exit_timeout_seconds"])
    for v in db.query(Visit).filter(Visit.status.in_(("provisional", "active"))).all():
        if now - v.last_seen > timeout:
            if v.status == "provisional":
                db.delete(v)  # never confirmed: not enough evidence of a real entry
                continue
            v.status = "exited"
            v.exit_at = v.last_seen
            dur = int((v.exit_at - v.entry_at).total_seconds())
            audit.append(db, "visit.ended", {"visit_id": v.id, "staff_id": v.staff_id, "ward_id": v.ward_id,
                                             "exit_at": iso(v.exit_at), "duration_seconds": dur,
                                             "fragments": v.fragments})
            hub.publish("visit.ended", serializers.visit(v), staff_scope=v.staff_id)
        elif v.status == "active":
            ward = v.ward
            limit = (ward.prolonged_stay_minutes if ward else 60) * 60
            if (now - v.entry_at).total_seconds() > limit and not (v.flags or {}).get("prolonged_alerted"):
                v.flags = {**(v.flags or {}), "prolonged_alerted": True}
                raise_alert(db, "prolonged_stay", "low",
                            f"{v.staff.name} has been in {ward.name} for over {ward.prolonged_stay_minutes} min",
                            ward_id=v.ward_id, camera_id=v.camera_id, staff_id=v.staff_id,
                            evidence={"visit_id": v.id}, dedup_key=f"prolonged:{v.id}")
    for t in db.query(Task).filter(Task.status.in_(("pending", "in_progress")), Task.due_at.isnot(None)).all():
        if t.due_at < now:
            _set_status(db, t, "overdue", "Deadline passed before evidence requirements were met")
            raise_alert(db, "task_overdue", "medium", f"Task '{t.title}' assigned to {t.staff.name} is overdue",
                        ward_id=t.ward_id, staff_id=t.staff_id, evidence={"task_id": t.id},
                        dedup_key=f"overdue:{t.id}")
    for cam in db.query(Camera).filter(Camera.enabled.is_(True)).all():
        stale = cam.last_frame_at is None or (now - cam.last_frame_at).total_seconds() > 20
        if stale and cam.status == "online":
            cam.status = "offline"
            hub.publish("camera.status", serializers.camera(cam))
            raise_alert(db, "camera_offline", "high", f"{cam.name} ({cam.code}) stopped sending frames",
                        ward_id=cam.ward_id, camera_id=cam.id,
                        dedup_key=f"camoff:{cam.id}:{iso(cam.last_frame_at)}")
    db.query(Track).filter(Track.active.is_(True), Track.last_seen < now - timedelta(seconds=60)).update(
        {Track.active: False}, synchronize_session=False)
