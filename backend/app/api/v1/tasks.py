from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import current_user, supervisor_up
from app.core.timeutil import parse_iso, utcnow
from app.db.models import Camera, Staff, Task, TaskEvidence, User, Ward
from app.db.session import get_db
from app.services import audit, serializers
from app.services.hub import hub

router = APIRouter(prefix="/tasks", tags=["tasks"])

TASK_TYPES = {
    "ward_inspection": {"min_duration_sec": 30, "requires_confirmation": False, "zone": None},
    "equipment_check": {"min_duration_sec": 20, "requires_confirmation": False, "zone": "equipment"},
    "medication_delivery": {"min_duration_sec": 30, "requires_confirmation": True, "zone": "bedside"},
}


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    task_type: str
    staff_id: int
    ward_id: int
    zone: str | None = None
    required_role: str | None = None
    min_duration_sec: int | None = Field(None, ge=5, le=7200)
    requires_confirmation: bool | None = None
    due_at: str | None = None
    notes: str = ""


class ReviewIn(BaseModel):
    decision: str  # approve | reject
    note: str = Field(min_length=3, max_length=500)


@router.get("/types")
def task_types(_=Depends(current_user)):
    return TASK_TYPES


@router.get("")
def list_tasks(status: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = db.query(Task)
    if user.access_role == "staff":
        q = q.filter(Task.staff_id == user.staff_id)
    if status:
        q = q.filter(Task.status == status)
    return [serializers.task(t) for t in q.order_by(Task.created_at.desc()).limit(500).all()]


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    t = db.get(Task, task_id)
    if t is None or (user.access_role == "staff" and t.staff_id != user.staff_id):
        raise HTTPException(404, "Task not found")
    return serializers.task(t, with_evidence=True)


@router.post("", status_code=201)
def create_task(body: TaskIn, db: Session = Depends(get_db), user: User = Depends(supervisor_up)):
    preset = TASK_TYPES.get(body.task_type)
    if preset is None:
        raise HTTPException(422, f"Task type must be one of {', '.join(TASK_TYPES)}")
    staff = db.get(Staff, body.staff_id)
    ward = db.get(Ward, body.ward_id)
    if staff is None or not staff.active:
        raise HTTPException(422, "Assign the task to an active staff member")
    if ward is None:
        raise HTTPException(422, "Select an existing ward")
    if body.required_role and staff.role != body.required_role:
        raise HTTPException(422, f"{staff.name} is a {staff.role}; this task requires a {body.required_role}")
    zone = body.zone if body.zone is not None else preset["zone"]
    zone = zone or None
    if zone:
        zones = {z["name"] for c in db.query(Camera).filter(Camera.ward_id == ward.id).all() for z in (c.zones or [])}
        if zone not in zones:
            raise HTTPException(422, f"No camera in {ward.name} defines a '{zone}' zone. Add it under Wards & cameras.")
    due = parse_iso(body.due_at)
    if due is not None and due <= utcnow():
        raise HTTPException(422, "Due time must be in the future")
    with audit.write_lock:
        t = Task(title=body.title, task_type=body.task_type, staff_id=staff.id, ward_id=ward.id, zone=zone,
                 required_role=body.required_role or None,
                 min_duration_sec=body.min_duration_sec or preset["min_duration_sec"],
                 requires_confirmation=preset["requires_confirmation"] if body.requires_confirmation is None
                 else body.requires_confirmation,
                 due_at=due, notes=body.notes, created_by=user.id)
        db.add(t)
        db.flush()
        audit.append(db, "task.created", {"task_id": t.id, "type": t.task_type, "staff_id": staff.id,
                                          "ward_id": ward.id, "zone": zone, "min_duration_sec": t.min_duration_sec,
                                          "requires_confirmation": t.requires_confirmation, "by": user.username})
        db.commit()
    db.refresh(t)
    out = serializers.task(t)
    hub.publish("task.updated", out, staff_scope=t.staff_id)
    return out


@router.post("/{task_id}/review")
def review(task_id: int, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(supervisor_up)):
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "Task not found")
    if body.decision not in ("approve", "reject"):
        raise HTTPException(422, "Decision must be approve or reject")
    if t.status in ("verified", "rejected"):
        raise HTTPException(409, f"Task is already {t.status}")
    if body.decision == "approve" and t.accumulated_seconds < t.min_duration_sec:
        raise HTTPException(409, "Required visual evidence has not been collected yet; it cannot be approved")
    with audit.write_lock:
        old = t.status
        t.status = "verified" if body.decision == "approve" else "rejected"
        t.completed_at = utcnow()
        db.add(TaskEvidence(task_id=t.id, evidence_type="supervisor_review",
                            detail=f"{body.decision} by {user.full_name}: {body.note}",
                            verification_state="confirmed" if body.decision == "approve" else "rejected"))
        audit.append(db, "task.reviewed", {"task_id": t.id, "from": old, "to": t.status, "note": body.note,
                                           "by": user.username})
        db.commit()
    db.refresh(t)
    out = serializers.task(t, with_evidence=True)
    hub.publish("task.updated", out, staff_scope=t.staff_id)
    return out
