"""Authenticated ingestion API for the vision worker. Never exposed to dashboard users."""
import base64
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import internal_auth
from app.core.security import decrypt_vector, encrypt_vector
from app.db.models import Camera, EnrollmentImage, FaceEmbedding, Staff
from app.db.session import get_db
from app.services import audit, engine, serializers, settings_service
from app.services.hub import hub
from app.services.runtime import frames, worker_state

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(internal_auth)])


@router.get("/config")
def config(db: Session = Depends(get_db)):
    return {
        "settings": settings_service.get_all(db),
        "cameras": [{"code": c.code, "source": c.source, "enabled": c.enabled, "ward_id": c.ward_id,
                     "zones": c.zones or []} for c in db.query(Camera).all()],
        "staff": [{"id": s.id, "staff_code": s.staff_code, "name": s.name, "role": s.role,
                   "ward_ids": [a.ward_id for a in s.access]} for s in db.query(Staff).filter(Staff.active.is_(True))],
    }


class Heartbeat(BaseModel):
    worker_id: str = "vision-worker"
    detector: str = ""
    tracker: str = ""
    face_model: str = ""
    device: str = ""
    cameras: dict = {}
    latency_ms: float | None = None


@router.post("/heartbeat")
def heartbeat(body: Heartbeat, db: Session = Depends(get_db)):
    worker_state["last_heartbeat"] = time.time()
    worker_state["info"] = body.model_dump()
    changed = []
    for code, st in body.cameras.items():
        c = db.query(Camera).filter(Camera.code == code).first()
        if c and st.get("error") and c.enabled and c.status != "offline":
            c.status = "offline"
            changed.append(c)
    if changed:
        db.commit()
        for c in changed:
            hub.publish("camera.status", {**serializers.camera(c), "error": body.cameras[c.code].get("error")})
    hub.publish("worker.heartbeat", worker_state["info"])
    return {"ok": True}


@router.post("/observations")
def observations(payload: dict, db: Session = Depends(get_db)):
    if "camera_id" not in payload:
        raise HTTPException(422, "camera_id required")
    with audit.write_lock:
        try:
            result = engine.process_observations(db, payload)
            db.commit()
        except Exception:
            db.rollback()
            raise
    return result


@router.post("/frames/{code}")
async def frame(code: str, request: Request):
    data = await request.body()
    if data[:2] != b"\xff\xd8":
        raise HTTPException(422, "Expected a JPEG body")
    frames.put(code, data)
    return {"ok": True}


@router.get("/enrollment/pending")
def pending(model: str, db: Session = Depends(get_db)):
    out = []
    for s in db.query(Staff).filter(Staff.active.is_(True), Staff.images.any()).all():
        if not any(e.model_version == model for e in s.embeddings):
            out.append(s.id)
    return {"staff_ids": out}


@router.get("/enrollment/{staff_id}/images")
def images(staff_id: int, db: Session = Depends(get_db)):
    rows = db.query(EnrollmentImage).filter(EnrollmentImage.staff_id == staff_id).all()
    out = []
    for r in rows:
        p = Path(r.path)
        if p.exists():
            out.append(base64.b64encode(p.read_bytes()).decode())
    return {"images": out}


class EmbeddingIn(BaseModel):
    model_version: str
    vector: list[float]
    num_images: int
    rejected_images: int = 0


@router.post("/enrollment/{staff_id}/embedding")
def save_embedding(staff_id: int, body: EmbeddingIn, db: Session = Depends(get_db)):
    s = db.get(Staff, staff_id)
    if s is None:
        raise HTTPException(404, "Staff not found")
    with audit.write_lock:
        db.query(FaceEmbedding).filter(FaceEmbedding.staff_id == staff_id,
                                       FaceEmbedding.model_version == body.model_version).delete()
        if body.num_images > 0:
            db.add(FaceEmbedding(staff_id=staff_id, model_version=body.model_version,
                                 encrypted_vector=encrypt_vector(body.vector), num_images=body.num_images))
        audit.append(db, "staff.enrolled" if body.num_images else "staff.enrollment_failed",
                     {"staff_id": staff_id, "staff_code": s.staff_code, "model": body.model_version,
                      "usable_images": body.num_images, "rejected_images": body.rejected_images})
        db.commit()
    db.refresh(s)
    hub.publish("staff.updated", {**serializers.staff(s), "enrollment_result": {
        "usable_images": body.num_images, "rejected_images": body.rejected_images}})
    return {"ok": True}


@router.get("/gallery")
def gallery(model: str, db: Session = Depends(get_db)):
    rows = (db.query(FaceEmbedding, Staff).join(Staff, Staff.id == FaceEmbedding.staff_id)
            .filter(FaceEmbedding.model_version == model, Staff.active.is_(True)).all())
    return {"model": model, "entries": [{"staff_id": s.id, "staff_code": s.staff_code, "name": s.name,
                                         "role": s.role, "vector": decrypt_vector(e.encrypted_vector)}
                                        for e, s in rows]}
