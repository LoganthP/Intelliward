from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import supervisor_up
from app.core.timeutil import iso, utcnow
from app.db.models import Alert, User
from app.db.session import get_db
from app.services import audit, serializers
from app.services.alerts import name_map
from app.services.hub import hub

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertPatch(BaseModel):
    status: str
    note: str = Field("", max_length=500)


@router.get("")
def list_alerts(status: str | None = None, severity: str | None = None, limit: int = 300,
                db: Session = Depends(get_db), _=Depends(supervisor_up)):
    q = db.query(Alert)
    if status == "active":
        q = q.filter(Alert.status.in_(("open", "acknowledged")))
    elif status:
        q = q.filter(Alert.status == status)
    if severity:
        q = q.filter(Alert.severity == severity)
    names = name_map(db)
    return [serializers.alert(a, names) for a in q.order_by(Alert.created_at.desc()).limit(min(limit, 1000)).all()]


@router.patch("/{alert_id}")
def update_alert(alert_id: int, body: AlertPatch, db: Session = Depends(get_db), user: User = Depends(supervisor_up)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(404, "Alert not found")
    if body.status not in ("acknowledged", "resolved", "dismissed", "open"):
        raise HTTPException(422, "Unknown status")
    if body.status in ("resolved", "dismissed") and len(body.note.strip()) < 3:
        raise HTTPException(422, "Add a short explanation when resolving or dismissing an alert")
    with audit.write_lock:
        old = a.status
        a.status = body.status
        a.updated_at = utcnow()
        a.history = [*(a.history or []), {"at": iso(a.updated_at), "status": body.status, "by": user.username,
                                          "note": body.note}]
        audit.append(db, "alert.updated", {"alert_id": a.id, "from": old, "to": body.status, "note": body.note,
                                           "by": user.username})
        db.commit()
    out = serializers.alert(a, name_map(db))
    hub.publish("alert.updated", out)
    return out
