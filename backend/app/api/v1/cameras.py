import asyncio
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import admin_only, current_user, supervisor_up, user_from_query
from app.db.models import Camera, Ward
from app.db.session import get_db
from app.services import audit, serializers
from app.services.hub import hub
from app.services.runtime import frames

router = APIRouter(prefix="/cameras", tags=["cameras"])


class Zone(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)


class CameraIn(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str
    ward_id: int
    source: str = "0"
    zones: list[Zone] = []


class CameraPatch(BaseModel):
    name: str | None = None
    ward_id: int | None = None
    source: str | None = None
    zones: list[Zone] | None = None


@router.get("")
def list_cameras(db: Session = Depends(get_db), _=Depends(current_user)):
    return [serializers.camera(c) for c in db.query(Camera).order_by(Camera.id).all()]


@router.post("", status_code=201)
def create_camera(body: CameraIn, db: Session = Depends(get_db), user=Depends(admin_only)):
    code = body.code.strip().upper()
    if db.query(Camera).filter(Camera.code == code).first():
        raise HTTPException(409, f"Camera {code} already exists")
    if db.get(Ward, body.ward_id) is None:
        raise HTTPException(422, "Select an existing ward")
    with audit.write_lock:
        c = Camera(code=code, name=body.name, ward_id=body.ward_id, source=body.source.strip() or "0",
                   zones=[z.model_dump() for z in body.zones])
        db.add(c)
        db.flush()
        audit.append(db, "camera.created", {"camera": code, "ward_id": body.ward_id, "by": user.username})
        db.commit()
    db.refresh(c)
    return serializers.camera(c)


@router.patch("/{camera_id}")
def update_camera(camera_id: int, body: CameraPatch, db: Session = Depends(get_db), user=Depends(admin_only)):
    c = db.get(Camera, camera_id)
    if c is None:
        raise HTTPException(404, "Camera not found")
    with audit.write_lock:
        if body.name is not None:
            c.name = body.name
        if body.ward_id is not None:
            if db.get(Ward, body.ward_id) is None:
                raise HTTPException(422, "Select an existing ward")
            c.ward_id = body.ward_id
        if body.source is not None:
            c.source = body.source.strip() or "0"
        if body.zones is not None:
            for z in body.zones:
                if z.x2 <= z.x1 or z.y2 <= z.y1:
                    raise HTTPException(422, f"Zone {z.name} must have x2 > x1 and y2 > y1")
            c.zones = [z.model_dump() for z in body.zones]
        audit.append(db, "camera.updated", {"camera": c.code, "by": user.username})
        db.commit()
    db.refresh(c)
    out = serializers.camera(c)
    hub.publish("camera.status", out)
    return out


def _set_enabled(db: Session, camera_id: int, enabled: bool, username: str):
    c = db.get(Camera, camera_id)
    if c is None:
        raise HTTPException(404, "Camera not found")
    with audit.write_lock:
        c.enabled = enabled
        c.status = "starting" if enabled else "stopped"
        if not enabled:
            c.fps = 0
            frames.drop(c.code)
        audit.append(db, "camera.started" if enabled else "camera.stopped", {"camera": c.code, "by": username})
        db.commit()
    db.refresh(c)
    out = serializers.camera(c)
    hub.publish("camera.status", out)
    return out


@router.post("/{camera_id}/start")
def start(camera_id: int, db: Session = Depends(get_db), user=Depends(supervisor_up)):
    return _set_enabled(db, camera_id, True, user.username)


@router.post("/{camera_id}/stop")
def stop(camera_id: int, db: Session = Depends(get_db), user=Depends(supervisor_up)):
    return _set_enabled(db, camera_id, False, user.username)


@router.post("/{camera_id}/video")
async def upload_video(camera_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                       user=Depends(admin_only)):
    c = db.get(Camera, camera_id)
    if c is None:
        raise HTTPException(404, "Camera not found")
    name = (file.filename or "video.mp4").lower()
    if not name.endswith((".mp4", ".avi", ".mov", ".mkv")):
        raise HTTPException(422, "Upload an MP4, AVI, MOV or MKV file")
    folder = settings.data_path / "videos"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{c.code}-{uuid.uuid4().hex[:8]}{name[name.rfind('.'):]}"
    with path.open("wb") as fh:
        while chunk := await file.read(1024 * 1024):
            fh.write(chunk)
    with audit.write_lock:
        c.source = str(path)
        audit.append(db, "camera.source_uploaded", {"camera": c.code, "file": path.name, "by": user.username})
        db.commit()
    db.refresh(c)
    return serializers.camera(c)


@router.get("/{code}/snapshot")
def snapshot(code: str, _=Depends(user_from_query)):
    item = frames.get(code)
    if item is None:
        raise HTTPException(404, "No frame yet")
    return Response(item[0], media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/{code}/stream")
async def stream(code: str, _=Depends(user_from_query)):
    boundary = "frame"

    async def gen():
        last_ts = 0.0
        idle = 0
        while idle < 600:  # stop after ~60s without new frames; the client reconnects
            item = frames.get(code)
            if item and item[1] != last_ts:
                last_ts = item[1]
                idle = 0
                yield (b"--" + boundary.encode() + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(item[0])).encode() + b"\r\n\r\n" + item[0] + b"\r\n")
            else:
                idle += 1
            await asyncio.sleep(0.1)

    return StreamingResponse(gen(), media_type=f"multipart/x-mixed-replace; boundary={boundary}",
                             headers={"Cache-Control": "no-store"})
