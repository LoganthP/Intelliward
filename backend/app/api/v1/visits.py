from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.timeutil import parse_iso, utcnow
from app.db.models import User, Visit
from app.db.session import get_db
from app.services import serializers

router = APIRouter(prefix="/visits", tags=["visits"])


def visit_query(db: Session, user: User, staff_id=None, ward_id=None, status=None, since=None, until=None):
    q = db.query(Visit).filter(Visit.status != "provisional")
    if user.access_role == "staff":
        q = q.filter(Visit.staff_id == user.staff_id)
    elif staff_id:
        q = q.filter(Visit.staff_id == staff_id)
    if ward_id:
        q = q.filter(Visit.ward_id == ward_id)
    if status:
        q = q.filter(Visit.status == status)
    if since:
        q = q.filter(Visit.entry_at >= parse_iso(since))
    if until:
        q = q.filter(Visit.entry_at <= parse_iso(until))
    return q.order_by(Visit.entry_at.desc())


@router.get("")
def list_visits(staff_id: int | None = None, ward_id: int | None = None, status: str | None = None,
                since: str | None = None, until: str | None = None, limit: int = Query(200, le=1000),
                db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not since:
        since = (utcnow() - timedelta(days=7)).isoformat() + "Z"
    return [serializers.visit(v) for v in visit_query(db, user, staff_id, ward_id, status, since, until).limit(limit)]
