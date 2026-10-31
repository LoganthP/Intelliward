import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import current_user, supervisor_up, admin_only
from app.core.security import hash_password
from app.db.models import EnrollmentImage, FaceEmbedding, Staff, StaffWardAccess, User
from app.db.session import get_db
from app.services import audit, serializers

router = APIRouter(prefix="/staff", tags=["staff"])
ROLES = {"nurse", "doctor", "ot_staff", "cleaner"}


class StaffIn(BaseModel):
    staff_code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=120)
    role: str
    department: str = ""
    consent_recorded: bool = False
    ward_ids: list[int] = []
    create_login: bool = False
    password: str | None = None


class StaffPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    department: str | None = None
    active: bool | None = None
    consent_recorded: bool | None = None
    ward_ids: list[int] | None = None


@router.get("")
def list_staff(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = db.query(Staff).order_by(Staff.staff_code)
    if user.access_role == "staff":
        q = q.filter(Staff.id == user.staff_id)
    return [serializers.staff(s) for s in q.all()]


@router.post("", status_code=201)
def create_staff(body: StaffIn, db: Session = Depends(get_db), user: User = Depends(supervisor_up)):
    if body.role not in ROLES:
        raise HTTPException(422, f"Role must be one of {', '.join(sorted(ROLES))}")
    code = body.staff_code.strip().upper()
    if db.query(Staff).filter(Staff.staff_code == code).first():
        raise HTTPException(409, f"Staff code {code} already exists")
    with audit.write_lock:
        s = Staff(staff_code=code, name=body.name.strip(), role=body.role, department=body.department,
                  consent_recorded=body.consent_recorded)
        db.add(s)
        db.flush()
        for wid in set(body.ward_ids):
            db.add(StaffWardAccess(staff_id=s.id, ward_id=wid))
        if body.create_login:
            if not body.password or len(body.password) < 6:
                raise HTTPException(422, "Login password must be at least 6 characters")
            uname = code.lower()
            if db.query(User).filter(User.username == uname).first():
                raise HTTPException(409, f"Login {uname} already exists")
            db.add(User(username=uname, full_name=s.name, access_role="staff",
                        password_hash=hash_password(body.password), staff_id=s.id))
        audit.append(db, "staff.created", {"staff_id": s.id, "staff_code": code, "role": body.role,
                                           "by": user.username})
        db.commit()
    db.refresh(s)
    return serializers.staff(s)


@router.patch("/{staff_id}")
def update_staff(staff_id: int, body: StaffPatch, db: Session = Depends(get_db), user: User = Depends(supervisor_up)):
    s = db.get(Staff, staff_id)
    if s is None:
        raise HTTPException(404, "Staff member not found")
    changes = body.model_dump(exclude_none=True)
    if "role" in changes and changes["role"] not in ROLES:
        raise HTTPException(422, "Unknown role")
    with audit.write_lock:
        for k, v in changes.items():
            if k != "ward_ids":
                setattr(s, k, v)
        if body.ward_ids is not None:
            db.query(StaffWardAccess).filter(StaffWardAccess.staff_id == s.id).delete()
            for wid in set(body.ward_ids):
                db.add(StaffWardAccess(staff_id=s.id, ward_id=wid))
        audit.append(db, "staff.updated", {"staff_id": s.id, "changes": changes, "by": user.username})
        db.commit()
    db.refresh(s)
    return serializers.staff(s)


@router.post("/{staff_id}/enroll")
async def enroll(staff_id: int, files: list[UploadFile] = File(...), db: Session = Depends(get_db),
                 user: User = Depends(supervisor_up)):
    s = db.get(Staff, staff_id)
    if s is None:
        raise HTTPException(404, "Staff member not found")
    if not s.consent_recorded:
        raise HTTPException(409, "Record the staff member's consent before enrolling face images")
    folder = settings.data_path / "enrollment" / s.staff_code
    folder.mkdir(parents=True, exist_ok=True)
    saved = 0
    for f in files[:10]:
        data = await f.read()
        if not data or len(data) > 8 * 1024 * 1024:
            continue
        if not (f.content_type or "").startswith("image/"):
            continue
        ext = ".png" if "png" in (f.content_type or "") else ".jpg"
        path = folder / f"{uuid.uuid4().hex}{ext}"
        path.write_bytes(data)
        db.add(EnrollmentImage(staff_id=s.id, path=str(path)))
        saved += 1
    if saved == 0:
        raise HTTPException(422, "Upload at least one JPG or PNG image under 8 MB")
    with audit.write_lock:
        # New images invalidate existing embeddings; the vision worker recomputes them.
        db.query(FaceEmbedding).filter(FaceEmbedding.staff_id == s.id).delete()
        audit.append(db, "staff.enrollment_images_added", {"staff_id": s.id, "count": saved, "by": user.username})
        db.commit()
    db.refresh(s)
    return {"saved": saved, "staff": serializers.staff(s),
            "message": "Images stored. The vision worker will compute the face template within a few seconds."}


@router.delete("/{staff_id}/enrollment")
def clear_enrollment(staff_id: int, db: Session = Depends(get_db), user: User = Depends(admin_only)):
    s = db.get(Staff, staff_id)
    if s is None:
        raise HTTPException(404, "Staff member not found")
    with audit.write_lock:
        for img in list(s.images):
            try:
                from pathlib import Path
                Path(img.path).unlink(missing_ok=True)
            except OSError:
                pass
        db.query(EnrollmentImage).filter(EnrollmentImage.staff_id == s.id).delete()
        db.query(FaceEmbedding).filter(FaceEmbedding.staff_id == s.id).delete()
        audit.append(db, "staff.enrollment_deleted", {"staff_id": s.id, "by": user.username})
        db.commit()
    db.refresh(s)
    return serializers.staff(s)
