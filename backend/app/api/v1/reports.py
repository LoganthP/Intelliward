import csv
import io
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import supervisor_up
from app.core.timeutil import iso, parse_iso, utcnow
from app.db.models import Alert, Task, Visit
from app.db.session import get_db
from app.services import audit, serializers
from app.services.alerts import name_map

router = APIRouter(prefix="/reports", tags=["reports"])


def _csv(rows: list[dict], columns: list[str], filename: str):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: (", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in r.items()})
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{kind}.csv")
def export(kind: str, since: str | None = None, db: Session = Depends(get_db), _=Depends(supervisor_up)):
    start = parse_iso(since) if since else utcnow() - timedelta(days=30)
    stamp = utcnow().strftime("%Y%m%d-%H%M")
    if kind == "visits":
        rows = [serializers.visit(v) for v in db.query(Visit).filter(Visit.entry_at >= start,
                                                                    Visit.status != "provisional").all()]
        return _csv(rows, ["id", "staff_code", "staff_name", "role", "ward_name", "entry_at", "exit_at",
                           "duration_seconds", "fragments", "status", "track_keys"], f"intelliward-visits-{stamp}.csv")
    if kind == "tasks":
        rows = [serializers.task(t) for t in db.query(Task).filter(Task.created_at >= start).all()]
        for r in rows:
            r["evidence_basis"] = ("authorized confirmation" if r["requires_confirmation"] and r["status"] == "verified"
                                   else "visual evidence only" if r["status"] == "verified" else "")
        return _csv(rows, ["id", "title", "task_type", "staff_code", "staff_name", "ward_name", "zone", "status",
                           "evidence_basis", "accumulated_seconds", "min_duration_sec", "due_at", "created_at",
                           "completed_at"], f"intelliward-tasks-{stamp}.csv")
    if kind == "alerts":
        names = name_map(db)
        rows = [serializers.alert(a, names) for a in db.query(Alert).filter(Alert.created_at >= start).all()]
        return _csv(rows, ["id", "alert_type", "severity", "status", "ward_name", "staff_name", "track_key",
                           "message", "created_at", "updated_at"], f"intelliward-alerts-{stamp}.csv")
    if kind == "audit":
        report = audit.verify_db(db)
        rows = [{"field": k, "value": v} for k, v in report.items() if k != "issues"]
        rows += [{"field": f"issue:{i['code']}", "value": f"seq {i['sequence']}: {i['message']}"}
                 for i in report["issues"]]
        rows.append({"field": "generated_at", "value": iso(utcnow())})
        return _csv(rows, ["field", "value"], f"intelliward-audit-summary-{stamp}.csv")
    raise HTTPException(404, "Report must be visits, tasks, alerts or audit")
