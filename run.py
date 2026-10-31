#!/usr/bin/env python3
"""IntelliWard launcher (Windows, macOS, Linux).

    python run.py setup               create .venv, install backend + worker + frontend, create .env files, fetch face models
    python run.py setup --ai          also install YOLOv8 + ByteTrack (Ultralytics / PyTorch)
    python run.py setup --insightface also try RetinaFace + ArcFace (InsightFace)
    python run.py dev                 start API, vision worker and dashboard together
    python run.py dev --simulate      same, but every camera uses the synthetic ward scenario
    python run.py backend | worker | frontend    start one service
    python run.py test                run backend, worker and frontend tests
    python run.py reset               delete the local database, anchors and enrollment images
"""
import os
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
IS_WIN = os.name == "nt"
PY = VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")
BACKEND, WORKER, FRONTEND = ROOT / "backend", ROOT / "vision-worker", ROOT / "frontend"
COLORS = {"api": "\033[36m", "worker": "\033[35m", "web": "\033[32m"}
RESET = "\033[0m"


def info(msg):
    print(f"\033[1m> {msg}{RESET}", flush=True)


def run(cmd, cwd=ROOT, check=True):
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], cwd=cwd, check=check)


def npm():
    exe = shutil.which("npm.cmd" if IS_WIN else "npm") or shutil.which("npm")
    if not exe:
        sys.exit("Node.js 18+ (with npm) is required. Install it from https://nodejs.org and reopen the terminal.")
    return exe


def find_python():
    if sys.version_info < (3, 13):
        return sys.executable
    for candidate in ["-V:Astral/CPython3.11.15", "-3.11", "-3.12"]:
        try:
            r = subprocess.run(["py", candidate, "-c", "import sys; print(sys.executable)"], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    uv_exe = shutil.which("uv")
    if uv_exe:
        try:
            r = subprocess.run([uv_exe, "python", "find", "3.11"], capture_output=True, text=True)
            path = r.stdout.strip()
            if r.returncode == 0 and path and Path(path).exists() and "site-packages" not in path:
                return path
        except Exception:
            pass
    return sys.executable


def check_python():
    v = sys.version_info
    if v < (3, 10):
        sys.exit(f"Python 3.10-3.12 is required (found {v.major}.{v.minor}).")
    if v >= (3, 13):
        print("! Python 3.13+ detected. Python 3.11 is strongly recommended for pre-compiled wheels (OpenCV, PyTorch).")


def ensure_env():
    be, we = BACKEND / ".env", WORKER / ".env"
    token = None
    if be.exists():
        for line in be.read_text().splitlines():
            if line.startswith("INTERNAL_TOKEN="):
                token = line.split("=", 1)[1].strip()
    if not be.exists():
        token = secrets.token_urlsafe(24)
        text = (BACKEND / ".env.example").read_text()
        text = text.replace("JWT_SECRET=change-me-intelliward-jwt-secret", f"JWT_SECRET={secrets.token_urlsafe(32)}")
        text = text.replace("INTERNAL_TOKEN=change-me-worker-token", f"INTERNAL_TOKEN={token}")
        be.write_text(text)
        info("Created backend/.env with fresh secrets")
    if not we.exists():
        text = (WORKER / ".env.example").read_text()
        if token:
            text = text.replace("INTERNAL_TOKEN=change-me-worker-token", f"INTERNAL_TOKEN={token}")
        we.write_text(text)
        info("Created vision-worker/.env (token matches the backend)")
    fe = FRONTEND / ".env"
    if not fe.exists():
        shutil.copy(FRONTEND / ".env.example", fe)


def setup(args):
    check_python()
    if not PY.exists():
        base_py = find_python()
        info(f"Creating virtual environment .venv (using {base_py})")
        run([base_py, "-m", "venv", VENV])
    run([PY, "-m", "pip", "install", "--upgrade", "pip", "wheel"])
    info("Installing backend dependencies")
    run([PY, "-m", "pip", "install", "-r", BACKEND / "requirements.txt"])
    info("Installing vision worker dependencies")
    run([PY, "-m", "pip", "install", "-r", WORKER / "requirements.txt"])
    if "--ai" in args:
        info("Installing YOLOv8 + ByteTrack (this downloads PyTorch, a few minutes)")
        run([PY, "-m", "pip", "install", "-r", WORKER / "requirements-ai.txt"])
    if "--insightface" in args:
        info("Installing InsightFace (optional)")
        r = run([PY, "-m", "pip", "install", "-r", WORKER / "requirements-insightface.txt"], check=False)
        if r.returncode:
            print("! InsightFace did not install. The worker will use OpenCV YuNet + SFace instead (fully supported).")
    ensure_env()
    info("Downloading OpenCV face models")
    r = run([PY, WORKER / "setup_models.py"], cwd=WORKER, check=False)
    if r.returncode:
        print("! Face models could not be downloaded now. Simulated cameras still work; rerun: python vision-worker/setup_models.py")
    info("Installing dashboard dependencies")
    run([npm(), "install", "--no-audit", "--no-fund"], cwd=FRONTEND)
    info("Setup complete. Start everything with:  python run.py dev")


def _pipe(name, proc):
    color = COLORS.get(name, "")
    for raw in iter(proc.stdout.readline, b""):
        line = raw.decode(errors="replace").rstrip()
        if line:
            print(f"{color}[{name:6}]{RESET} {line}", flush=True)


def start(name, cmd, cwd, env=None):
    kw = {"cwd": cwd, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "env": {**os.environ, **(env or {})}}
    if IS_WIN:
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen([str(c) for c in cmd], **kw)
    threading.Thread(target=_pipe, args=(name, p), daemon=True).start()
    return p


def stop(procs):
    for p in procs:
        if p.poll() is None:
            try:
                if IS_WIN:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
                else:
                    os.killpg(p.pid, signal.SIGTERM)
            except Exception:
                p.terminate()


def wait_for_api(timeout=40):
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/system/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.7)
    return False


def services(which, args):
    if not PY.exists():
        sys.exit("Run `python run.py setup` first.")
    test_proc = subprocess.run([PY, "-c", "import fastapi, cv2"], capture_output=True)
    if test_proc.returncode != 0:
        sys.exit("Dependencies are missing or setup was incomplete. Please run `python run.py setup` (or `python run.py setup --ai`) first and let it finish.")
    ensure_env()
    procs = []
    unbuffered = {"PYTHONUNBUFFERED": "1"}
    try:
        if "api" in which:
            procs.append(start("api", [PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--no-access-log"],
                               BACKEND, unbuffered))
            if not wait_for_api():
                print("! The API did not become healthy in time. Check the [api] lines above.")
        if "worker" in which:
            cmd = [PY, "worker.py"] + (["--simulate"] if "--simulate" in args else [])
            procs.append(start("worker", cmd, WORKER, unbuffered))
        if "web" in which:
            procs.append(start("web", [npm(), "run", "dev"], FRONTEND))
            info("Dashboard: http://localhost:5173   API docs: http://localhost:8000/docs   (Ctrl+C stops everything)")
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"! A service exited with code {p.returncode}. Stopping the others.")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        info("Stopping services")
        stop(procs)


def test(_):
    ok = True
    ok &= run([PY, "-m", "pytest", "-q", "tests"], cwd=BACKEND, check=False).returncode == 0
    ok &= run([PY, "-m", "pytest", "-q", "tests"], cwd=WORKER, check=False).returncode == 0
    ok &= run([npm(), "run", "typecheck"], cwd=FRONTEND, check=False).returncode == 0
    ok &= run([npm(), "test"], cwd=FRONTEND, check=False).returncode == 0
    info("All tests passed" if ok else "Some tests failed")
    sys.exit(0 if ok else 1)


def reset(_):
    data = ROOT / "data"
    ans = input(f"Delete {data} (database, anchors, enrollment images, uploaded videos)? Type yes: ")
    if ans.strip().lower() == "yes":
        shutil.rmtree(data, ignore_errors=True)
        info("Local data deleted. Demo data is re-seeded on the next API start.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "setup":
        setup(args)
    elif cmd == "dev":
        services({"api", "worker", "web"}, args)
    elif cmd == "backend":
        services({"api"}, args)
    elif cmd == "worker":
        services({"worker"}, args)
    elif cmd == "frontend":
        services({"web"}, args)
    elif cmd == "test":
        test(args)
    elif cmd == "reset":
        reset(args)
    else:
        print(__doc__)


if __name__ == "__main__":
    if IS_WIN:
        os.system("")  # enable ANSI colours in Windows terminals
    main()
