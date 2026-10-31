from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import admin_only, current_user
from app.db.models import Ward
from app.db.session import get_db
from app.services import audit, serializers

router = APIRouter(prefix="/wards", tags=["wards"])


class WardIn(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2)
    location: str = ""
    restricted: bool = False
    prolonged_stay_minutes: int = Field(60, ge=1, le=1440)


@router.get("")
def list_wards(db: Session = Depends(get_db), _=Depends(current_user)):
    return [serializers.ward(w) for w in db.query(Ward).order_by(Ward.id).all()]


@router.post("", status_code=201)
def create_ward(body: WardIn, db: Session = Depends(get_db), user=Depends(admin_only)):
    code = body.code.strip().upper()
    if db.query(Ward).filter(Ward.code == code).first():
        raise HTTPException(409, f"Ward {code} already exists")
    with audit.write_lock:
        w = Ward(code=code, name=body.name, location=body.location, restricted=body.restricted,
                 prolonged_stay_minutes=body.prolonged_stay_minutes)
        db.add(w)
        db.flush()
        audit.append(db, "ward.created", {"ward_id": w.id, "code": code, "by": user.username})
        db.commit()
    return serializers.ward(w)


@router.patch("/{ward_id}")
def update_ward(ward_id: int, body: WardIn, db: Session = Depends(get_db), user=Depends(admin_only)):
    w = db.get(Ward, ward_id)
    if w is None:
        raise HTTPException(404, "Ward not found")
    with audit.write_lock:
        w.name, w.location, w.restricted = body.name, body.location, body.restricted
        w.prolonged_stay_minutes = body.prolonged_stay_minutes
        audit.append(db, "ward.updated", {"ward_id": w.id, "by": user.username})
        db.commit()
    return serializers.ward(w)
