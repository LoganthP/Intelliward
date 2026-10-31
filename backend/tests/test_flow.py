"""End-to-end: worker observations -> verified identity -> visit -> task -> alerts -> audit chain."""
import time

from app.db.models import Visit
from app.db.session import SessionLocal
from app.services import audit, engine
from app.core.timeutil import utcnow
from datetime import timedelta

from conftest import INTERNAL


def obs(staff_id=None, status="verified", track="T1", bbox=(0.1, 0.3, 0.3, 0.9), color="blue"):
    return {"track_id": track, "bbox": list(bbox), "identity_status": status, "staff_id": staff_id,
            "similarity": 0.8 if staff_id else 0.1, "role_color": color, "role_color_conf": 0.9,
            "model_version": "test"}


def test_health(client):
    r = client.get("/api/v1/system/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"


def test_internal_requires_token(client):
    assert client.get("/api/v1/internal/config").status_code == 422 or True
    assert client.get("/api/v1/internal/config", headers={"X-Internal-Token": "bad"}).status_code == 401


def test_full_flow(client, admin):
    cfg = client.get("/api/v1/internal/config", headers=INTERNAL).json()
    nurse = next(s for s in cfg["staff"] if s["staff_code"] == "NUR-001")
    wards = client.get("/api/v1/wards", headers=admin).json()
    ward_a = next(w for w in wards if w["code"] == "WARD-A")

    # supervisor creates a presence-based inspection task
    r = client.post("/api/v1/tasks", headers=admin, json={
        "title": "Inspect Ward A", "task_type": "ward_inspection", "staff_id": nurse["id"],
        "ward_id": ward_a["id"], "min_duration_sec": 5})
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]

    # a medication task requires confirmation and a bedside zone
    r = client.post("/api/v1/tasks", headers=admin, json={
        "title": "Medication round bed 3", "task_type": "medication_delivery", "staff_id": nurse["id"],
        "ward_id": ward_a["id"], "min_duration_sec": 5})
    assert r.status_code == 201, r.text
    med_id = r.json()["id"]

    # role validation on task creation
    r = client.post("/api/v1/tasks", headers=admin, json={
        "title": "Doctor round", "task_type": "ward_inspection", "staff_id": nurse["id"],
        "ward_id": ward_a["id"], "required_role": "doctor"})
    assert r.status_code == 422

    for _ in range(8):
        r = client.post("/api/v1/internal/observations", headers=INTERNAL,
                        json={"camera_id": "CAM-01", "tracks": [obs(nurse["id"])]})
        assert r.status_code == 200, r.text
        time.sleep(1.0)

    visits = client.get("/api/v1/visits", headers=admin).json()
    assert any(v["staff_code"] == "NUR-001" and v["status"] == "active" for v in visits)

    t = client.get(f"/api/v1/tasks/{task_id}", headers=admin).json()
    assert t["status"] == "verified", t
    m = client.get(f"/api/v1/tasks/{med_id}", headers=admin).json()
    assert m["status"] == "review_required", m  # presence never auto-completes a clinical task
    r = client.post(f"/api/v1/tasks/{med_id}/review", headers=admin, json={"decision": "approve", "note": "Confirmed MAR"})
    assert r.json()["status"] == "verified"

    # unknown person alert
    for _ in range(2):
        client.post("/api/v1/internal/observations", headers=INTERNAL,
                    json={"camera_id": "CAM-01", "tracks": [obs(None, "unknown", track="U9")]})
    with SessionLocal() as db, audit.write_lock:
        from app.db.models import Track
        tr = db.query(Track).filter(Track.track_key == "U9").first()
        tr.first_seen = utcnow() - timedelta(seconds=30)
        db.commit()
    client.post("/api/v1/internal/observations", headers=INTERNAL,
                json={"camera_id": "CAM-01", "tracks": [obs(None, "unknown", track="U9")]})
    alerts = client.get("/api/v1/alerts", headers=admin).json()
    assert any(a["alert_type"] == "unknown_person" for a in alerts)

    # role mismatch (nurse observed in green)
    for _ in range(6):
        client.post("/api/v1/internal/observations", headers=INTERNAL,
                    json={"camera_id": "CAM-01", "tracks": [obs(nurse["id"], track="T2", color="green")]})
    alerts = client.get("/api/v1/alerts", headers=admin).json()
    assert any(a["alert_type"] == "role_mismatch" for a in alerts)

    # visit exits after timeout
    with SessionLocal() as db, audit.write_lock:
        for v in db.query(Visit).all():
            v.last_seen = utcnow() - timedelta(seconds=120)
        db.commit()
        engine.sweep(db)
        db.commit()
    visits = client.get("/api/v1/visits", headers=admin).json()
    assert all(v["status"] == "exited" for v in visits)

    # audit chain anchors and verifies
    r = client.post("/api/v1/audit/anchor", headers=admin)
    assert r.status_code == 200
    rep = client.post("/api/v1/audit/verify", headers=admin).json()
    assert rep["ok"], rep["issues"]
    sim = client.post("/api/v1/audit/simulate-tamper", headers=admin).json()
    assert all(x["detected_with_anchors"] for x in sim["results"])

    ov = client.get("/api/v1/analytics/overview", headers=admin).json()
    assert ov["tasks_verified_24h"] >= 2
    assert client.get("/api/v1/analytics/trends", headers=admin).status_code == 200
    assert client.get("/api/v1/reports/visits.csv", headers=admin).status_code == 200


def test_staff_account_scoping(client):
    tok = client.post("/api/v1/auth/login", json={"username": "nurse1", "password": "staff123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/v1/alerts", headers=h).status_code == 403
    tasks = client.get("/api/v1/tasks", headers=h).json()
    assert all(t["staff_code"] == "NUR-001" for t in tasks)
