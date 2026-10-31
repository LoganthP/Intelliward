"""Idempotent demo seed: accounts, wards, cameras, sample staff and access rules."""
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.timeutil import utcnow

from app.core.security import hash_password
from app.db.models import Camera, Staff, StaffWardAccess, Task, User, Ward
from . import audit

DEMO_USERS = [
    ("admin", "Hospital Administrator", "admin", "admin123", None),
    ("supervisor", "Ward Supervisor", "supervisor", "super123", None),
    ("nurse1", "Asha Rao", "staff", "staff123", "NUR-001"),
]

DEMO_STAFF = [
    ("NUR-001", "Asha Rao", "nurse", "General Medicine"),
    ("DOC-001", "Dr. Vikram Shetty", "doctor", "Internal Medicine"),
    ("OT-001", "Kiran Kumar", "ot_staff", "Surgery"),
    ("CLN-001", "Meena Gowda", "cleaner", "Housekeeping"),
]

DEMO_WARDS = [
    ("WARD-A", "Ward A", "Block 1, Floor 2", False, 60),
    ("ICU", "Intensive Care Unit", "Block 2, Floor 1", True, 90),
    ("OT-1", "Operation Theatre 1", "Block 3, Floor 1", True, 240),
]

DEFAULT_ZONES = [
    {"name": "bedside", "x1": 0.0, "y1": 0.45, "x2": 0.45, "y2": 1.0},
    {"name": "equipment", "x1": 0.6, "y1": 0.45, "x2": 1.0, "y2": 1.0},
]


def seed(db: Session) -> None:
    if db.query(User).count() > 0:
        return
    with audit.write_lock:
        wards = {}
        for code, name, loc, restricted, prolonged in DEMO_WARDS:
            w = Ward(code=code, name=name, location=loc, restricted=restricted, prolonged_stay_minutes=prolonged)
            db.add(w)
            wards[code] = w
        db.flush()
        staff = {}
        for code, name, role, dept in DEMO_STAFF:
            s = Staff(staff_code=code, name=name, role=role, department=dept, consent_recorded=True)
            db.add(s)
            staff[code] = s
        db.flush()
        for code in staff:
            db.add(StaffWardAccess(staff_id=staff[code].id, ward_id=wards["WARD-A"].id))
        db.add(StaffWardAccess(staff_id=staff["DOC-001"].id, ward_id=wards["ICU"].id))
        db.add(StaffWardAccess(staff_id=staff["NUR-001"].id, ward_id=wards["ICU"].id))
        db.add(StaffWardAccess(staff_id=staff["OT-001"].id, ward_id=wards["OT-1"].id))
        db.add(Camera(code="CAM-01", name="Ward A entrance", ward_id=wards["WARD-A"].id, source="0",
                      zones=DEFAULT_ZONES))
        # CAM-02 runs the synthetic scenario so the whole workflow is visible before any webcam is connected.
        db.add(Camera(code="CAM-02", name="ICU simulated feed", ward_id=wards["ICU"].id, source="sim",
                      enabled=True, status="starting", zones=DEFAULT_ZONES))
        for username, full, role, pwd, staff_code in DEMO_USERS:
            db.add(User(username=username, full_name=full, access_role=role, password_hash=hash_password(pwd),
                        staff_id=staff[staff_code].id if staff_code else None))
        db.flush()
        due = utcnow() + timedelta(hours=8)
        demo_tasks = [
            Task(title="ICU safety inspection", task_type="ward_inspection", staff_id=staff["NUR-001"].id,
                 ward_id=wards["ICU"].id, min_duration_sec=30, requires_confirmation=False, due_at=due),
            Task(title="Medication round, ICU bed 2", task_type="medication_delivery", staff_id=staff["NUR-001"].id,
                 ward_id=wards["ICU"].id, zone="bedside", min_duration_sec=25, requires_confirmation=True, due_at=due),
            Task(title="Ventilator check", task_type="equipment_check", staff_id=staff["NUR-001"].id,
                 ward_id=wards["ICU"].id, zone="equipment", min_duration_sec=20, requires_confirmation=False, due_at=due),
        ]
        db.add_all(demo_tasks)
        db.flush()
        audit.append(db, "system.seeded", {"wards": list(wards), "staff": list(staff),
                                           "tasks": [t.id for t in demo_tasks]})
        db.commit()
