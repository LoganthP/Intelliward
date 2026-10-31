from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import admin_only, supervisor_up
from app.core.timeutil import iso, utcnow
from app.db.models import AuditBatch, AuditEvent, User
from app.db.session import get_db
from app.integrity.tamper import run_simulations
from app.services import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
def events(before: int | None = None, limit: int = Query(50, le=200), event_type: str | None = None,
           db: Session = Depends(get_db), _=Depends(supervisor_up)):
    q = db.query(AuditEvent)
    if before:
        q = q.filter(AuditEvent.sequence < before)
    if event_type:
        q = q.filter(AuditEvent.event_type == event_type)
    last_anchor = db.query(AuditBatch).order_by(AuditBatch.id.desc()).first()
    anchored_to = last_anchor.last_sequence if last_anchor else 0
    return [{"sequence": e.sequence, "event_id": e.event_id, "event_type": e.event_type,
             "occurred_at": iso(e.occurred_at), "payload": e.payload, "prev_hash": e.prev_hash,
             "curr_hash": e.curr_hash, "anchored": e.sequence <= anchored_to}
            for e in q.order_by(AuditEvent.sequence.desc()).limit(limit).all()]


@router.get("/batches")
def batches(db: Session = Depends(get_db), _=Depends(supervisor_up)):
    return {"database": [{"id": b.id, "first_sequence": b.first_sequence, "last_sequence": b.last_sequence,
                          "merkle_root": b.merkle_root, "anchor_hash": b.anchor_hash,
                          "external_reference": b.external_reference, "created_at": iso(b.created_at)}
                         for b in db.query(AuditBatch).order_by(AuditBatch.id.desc()).limit(100).all()],
            "external": list(reversed(audit.anchor_store.read_all()))[:100]}


@router.post("/verify")
def verify(db: Session = Depends(get_db), user: User = Depends(supervisor_up)):
    report = audit.verify_db(db)
    report["verified_at"] = iso(utcnow())
    if report["ok"]:
        audit.committed_append(db, "audit.verified", {"ok": True, "events": report["events_checked"],
                                                      "by": user.username})
    # On failure we deliberately do not append: diagnostics are returned and the damaged history is left untouched.
    return report


@router.post("/anchor")
def anchor_now(db: Session = Depends(get_db), _=Depends(supervisor_up)):
    try:
        batch = audit.anchor_pending(db, force=True)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    if batch is None:
        return {"anchored": False, "message": "Every event is already anchored"}
    return {"anchored": True, "batch_id": batch.id, "first_sequence": batch.first_sequence,
            "last_sequence": batch.last_sequence, "merkle_root": batch.merkle_root}


@router.post("/simulate-tamper")
def simulate(db: Session = Depends(get_db), user: User = Depends(admin_only)):
    try:
        audit.anchor_pending(db, force=True)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    events, batches, anchors = audit.snapshot(db)
    if len(events) < 6 or not anchors:
        raise HTTPException(409, "Need at least 6 anchored audit events. Use the system for a minute and retry.")
    results = run_simulations(events, batches, anchors)
    audit.committed_append(db, "audit.tamper_simulation", {
        "by": user.username, "events": len(events),
        "detected_with_anchors": sum(r["detected_with_anchors"] for r in results),
        "attacks": len(results)})
    return {"events": len(events), "batches": len(batches), "results": results}
