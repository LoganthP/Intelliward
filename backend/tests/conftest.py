import os
import shutil
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="intelliward-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TMP / 'test.db').as_posix()}"
os.environ["DATA_DIR"] = str(TMP / "data")
os.environ["ANCHOR_DIR"] = str(TMP / "anchors")
os.environ["INTERNAL_TOKEN"] = "test-token"
os.environ["RUN_BACKGROUND"] = "false"
os.environ["AUDIT_BATCH_SIZE"] = "5"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    shutil.rmtree(TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def admin(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


INTERNAL = {"X-Internal-Token": "test-token"}
