from collections import Counter, defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import current_user, supervisor_up
from app.core.timeutil import iso, utcnow
from app.db.models import Alert, AuditEvent, Camera, Staff, Task, User, Visit
from app.db.session import get_db
from app.services.runtime import worker_online

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(current_user)):
    now = utcnow()
    day_start = now - timedelta(hours=24)
    if user.access_role == "staff":
        my_tasks = db.query(Task).filter(Task.staff_id == user.staff_id)
        return {
            "scope": "self",
            "tasks_open": my_tasks.filter(Task.status.in_(("pending", "in_progress", "review_required", "overdue"))).count(),
            "tasks_verified_24h": my_tasks.filter(Task.status == "verified", Task.completed_at >= day_start).count(),
            "visits_24h": db.query(Visit).filter(Visit.staff_id == user.staff_id, Visit.entry_at >= day_start,
                                                 Visit.status != "provisional").count(),
            "present": db.query(Visit).filter(Visit.staff_id == user.staff_id, Visit.status == "active").count() > 0,
        }
    cams = db.query(Camera).all()
    active_visits = db.query(Visit).filter(Visit.status == "active").all()
    finished = db.query(Visit).filter(Visit.status == "exited", Visit.entry_at >= day_start).all()
    durations = [(v.exit_at - v.entry_at).total_seconds() for v in finished if v.exit_at]
    return {
        "scope": "hospital",
        "cameras_total": len(cams),
        "cameras_online": sum(1 for c in cams if c.status == "online"),
        "staff_total": db.query(Staff).filter(Staff.active.is_(True)).count(),
        "staff_enrolled": db.query(Staff).filter(Staff.embeddings.any()).count(),
        "staff_present": len({v.staff_id for v in active_visits}),
        "present_now": [{"staff_id": v.staff_id, "name": v.staff.name, "code": v.staff.staff_code,
                         "role": v.staff.role, "ward": v.ward.name, "since": iso(v.entry_at)} for v in active_visits],
        "alerts_open": db.query(Alert).filter(Alert.status.in_(("open", "acknowledged"))).count(),
        "alerts_high_open": db.query(Alert).filter(Alert.status == "open",
                                                   Alert.severity.in_(("high", "critical"))).count(),
        "tasks_verified_24h": db.query(Task).filter(Task.status == "verified", Task.completed_at >= day_start).count(),
        "tasks_open": db.query(Task).filter(Task.status.in_(("pending", "in_progress"))).count(),
        "tasks_review": db.query(Task).filter(Task.status == "review_required").count(),
        "tasks_overdue": db.query(Task).filter(Task.status == "overdue").count(),
        "visits_24h": len(finished) + len(active_visits),
        "avg_visit_seconds": int(sum(durations) / len(durations)) if durations else 0,
        "audit_events": db.query(func.count(AuditEvent.sequence)).scalar() or 0,
        "worker_online": worker_online(),
    }


@router.get("/trends")
def trends(days: int = 7, db: Session = Depends(get_db), _=Depends(supervisor_up)):
    days = max(1, min(days, 30))
    now = utcnow()
    since = now - timedelta(days=days)
    visits = db.query(Visit).filter(Visit.entry_at >= since, Visit.status != "provisional").all()
    alerts = db.query(Alert).filter(Alert.created_at >= since).all()
    tasks = db.query(Task).filter(Task.created_at >= since).all()

    hourly = Counter()
    for v in visits:
        if v.entry_at >= now - timedelta(hours=24):
            hourly[v.entry_at.replace(minute=0, second=0, microsecond=0)] += 1
    hours = [(now - timedelta(hours=h)).replace(minute=0, second=0, microsecond=0) for h in range(23, -1, -1)]

    daily_alerts = defaultdict(Counter)
    for a in alerts:
        daily_alerts[a.created_at.date().isoformat()][a.severity] += 1
    day_keys = [(now - timedelta(days=d)).date().isoformat() for d in range(days - 1, -1, -1)]

    presence = defaultdict(float)
    for v in visits:
        end = v.exit_at or v.last_seen
        presence[(v.staff.staff_code, v.staff.name)] += max(0.0, (end - v.entry_at).total_seconds()) / 60

    ward_minutes = defaultdict(float)
    for v in visits:
        end = v.exit_at or v.last_seen
        ward_minutes[v.ward.name] += max(0.0, (end - v.entry_at).total_seconds()) / 60

    return {
        "visits_by_hour": [{"hour": iso(h), "visits": hourly.get(h, 0)} for h in hours],
        "alerts_by_day": [{"day": d, **{s: daily_alerts[d].get(s, 0) for s in ("low", "medium", "high", "critical")}}
                          for d in day_keys],
        "alerts_by_type": [{"type": k, "count": c} for k, c in Counter(a.alert_type for a in alerts).most_common()],
        "tasks_by_status": [{"status": k, "count": c} for k, c in Counter(t.status for t in tasks).most_common()],
        "presence_by_staff": sorted([{"code": k[0], "name": k[1], "minutes": round(m, 1)} for k, m in presence.items()],
                                    key=lambda x: -x["minutes"])[:12],
        "minutes_by_ward": [{"ward": k, "minutes": round(m, 1)} for k, m in ward_minutes.items()],
    }
