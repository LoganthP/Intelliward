from sqlalchemy.orm import Session

from app.core.timeutil import iso, utcnow
from app.db.models import Alert, Staff, Ward
from . import audit, serializers
from .hub import hub


def name_map(db: Session) -> dict:
    out = {}
    for w in db.query(Ward.id, Ward.name).all():
        out[("ward", w.id)] = w.name
    for s in db.query(Staff.id, Staff.name).all():
        out[("staff", s.id)] = s.name
    return out


def raise_alert(db: Session, alert_type: str, severity: str, message: str, *, ward_id=None, camera_id=None,
                staff_id=None, track_key=None, evidence: dict | None = None, dedup_key: str | None = None):
    """Create an alert once per dedup_key. Caller holds audit.write_lock and commits."""
    if dedup_key and db.query(Alert.id).filter(Alert.dedup_key == dedup_key).first():
        return None
    now = utcnow()
    a = Alert(alert_type=alert_type, severity=severity, message=message, ward_id=ward_id, camera_id=camera_id,
              staff_id=staff_id, track_key=track_key, evidence=evidence or {}, dedup_key=dedup_key,
              created_at=now, updated_at=now, history=[{"at": iso(now), "status": "open", "by": "system"}])
    db.add(a)
    db.flush()
    audit.append(db, "alert.created", {"alert_id": a.id, "type": alert_type, "severity": severity,
                                       "ward_id": ward_id, "staff_id": staff_id, "track_key": track_key})
    hub.publish("alert.created", serializers.alert(a, name_map(db)))
    return a
