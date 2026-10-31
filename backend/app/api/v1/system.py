import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import admin_only, current_user
from app.db.models import Camera
from app.db.session import get_db
from app.services import serializers, settings_service
from app.services.runtime import worker_online, worker_state

router = APIRouter(tags=["system"])


@router.get("/system/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    info = worker_state.get("info", {})
    return {
        "api": "ok",
        "database": "ok" if db_ok else "error",
        "database_engine": settings.db_url.split(":")[0],
        "worker": "online" if worker_online() else "offline",
        "worker_last_seen_seconds": round(time.time() - worker_state["last_heartbeat"], 1)
        if worker_state["last_heartbeat"] else None,
        "worker_info": info,
        "cameras": [serializers.camera(c) for c in db.query(Camera).all()],
    }


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _=Depends(current_user)):
    return settings_service.get_all(db)


@router.patch("/settings")
def patch_settings(body: dict, db: Session = Depends(get_db), user=Depends(admin_only)):
    from fastapi import HTTPException
    from app.services import audit
    try:
        with audit.write_lock:
            out = settings_service.update(db, body)
            audit.append(db, "settings.updated", {"changes": body, "by": user.username})
            db.commit()
    except KeyError as exc:
        raise HTTPException(422, f"Unknown setting {exc}")
    return out
