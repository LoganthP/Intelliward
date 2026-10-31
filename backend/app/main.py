import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import alerts, analytics, audit as audit_api, auth, cameras, internal, reports, staff, system, tasks, visits, wards, ws
from app.core.config import settings
from app.db import models  # noqa: F401  (register tables)
from app.db.session import Base, SessionLocal, engine
from app.services import audit, engine as rules
from app.services.hub import hub
from app.services.seed import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("intelliward")
_stop = threading.Event()


def background_loop():
    """Visit exits, overdue tasks, camera health and audit anchoring."""
    while not _stop.wait(settings.background_interval_seconds):
        db = SessionLocal()
        try:
            with audit.write_lock:
                rules.sweep(db)
                db.commit()
            audit.anchor_pending(db)
        except Exception:
            db.rollback()
            log.exception("background sweep failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    hub.bind_loop(asyncio.get_running_loop())
    thread = None
    if settings.run_background:
        _stop.clear()
        thread = threading.Thread(target=background_loop, name="intelliward-sweeper", daemon=True)
        thread.start()
    log.info("IntelliWard API ready (database: %s)", settings.db_url.split(":")[0])
    yield
    _stop.set()
    if thread:
        thread.join(timeout=5)


app = FastAPI(title="IntelliWard API", version="1.0.0", lifespan=lifespan,
              description="AI-powered hospital staff monitoring, task verification and tamper-evident logging")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error. Check the API log."})


for r in (auth.router, staff.router, wards.router, cameras.router, visits.router, tasks.router, alerts.router,
          analytics.router, audit_api.router, system.router, reports.router, internal.router):
    app.include_router(r, prefix="/api/v1")
app.include_router(ws.router)


@app.get("/")
def root():
    return {"name": "IntelliWard API", "docs": "/docs", "health": "/api/v1/system/health"}
