# IntelliWard

**AI-Powered Smart Hospital Staff Monitoring and Task Verification with Tamper-Evident Logging**
Final-year CSE major project prototype: Vidyavardhaka College of Engineering, Mysuru.

The working chain this prototype demonstrates:

```
Camera observation → Verified identity → Role & ward → Visit → Task evidence → Audit trail → Live dashboard
```

| Part | Technology | Folder |
|---|---|---|
| Dashboard | React 18 + TypeScript + Vite + Tailwind + Framer Motion + Recharts | `frontend/` |
| API | Python FastAPI, SQLAlchemy, WebSockets, JWT | `backend/` |
| Vision worker | OpenCV, YOLOv8 + ByteTrack (Ultralytics), RetinaFace + ArcFace (InsightFace) or YuNet + SFace (OpenCV), HSV uniform cue | `vision-worker/` |
| Integrity | SHA-256 hash chain, Merkle batches, independent append-only anchors | `backend/app/integrity/` |
| Database | SQLite by default (zero setup), PostgreSQL via `docker-compose.yml` | `data/` |

---

## 1. Requirements

* **Python 3.10, 3.11 or 3.12** (3.11 recommended). Check with `python --version`.
* **Node.js 18 or newer** (20 LTS recommended). Check with `node --version`.
* Windows 11, macOS or Linux. A GPU is optional.
* Internet access the first time (packages and model downloads).

On Windows, when installing Python tick **"Add python.exe to PATH"**.

## 2. Install (one command)

Open a terminal in the `IntelliWard` folder:

```bash
python run.py setup --ai
```

This creates `.venv`, installs the backend, the vision worker with YOLOv8 + ByteTrack, the dashboard packages,
creates `backend/.env` and `vision-worker/.env` with matching random secrets, and downloads the OpenCV face models.

* Quicker install without PyTorch: `python run.py setup` (simulated cameras and OpenCV face recognition still work; real cameras use the fallback detector).
* Optional InsightFace (RetinaFace + ArcFace): `python run.py setup --ai --insightface`. On Windows it needs *Microsoft C++ Build Tools*. If it fails, nothing breaks; the worker uses YuNet + SFace.
* NVIDIA GPU: after setup, install the CUDA build of PyTorch into `.venv` following the selector at pytorch.org. The worker detects CUDA automatically (`DEVICE=auto`).

## 3. Run

```bash
python run.py dev
```

| Service | Address |
|---|---|
| Dashboard | http://localhost:5173 |
| API | http://localhost:8000 |
| API documentation | http://localhost:8000/docs |

`Ctrl+C` stops all three services. To start them separately (three terminals):

```bash
python run.py backend
python run.py worker          # add --simulate to force every camera into the synthetic scenario
python run.py frontend
```

### Demo accounts

| Username | Password | Can do |
|---|---|---|
| `admin` | `admin123` | Everything, including settings, cameras and the tamper test |
| `supervisor` | `super123` | Staff, tasks, reviews, alerts, audit verification |
| `nurse1` | `staff123` | Sees only their own tasks and visits |

Change them before showing the system to anyone outside the team.

## 4. What you see on first start

The database seeds three wards (Ward A, ICU restricted, OT-1 restricted), four staff members, demo tasks and two cameras:

* **CAM-02, ICU simulated feed** starts automatically. It plays a 150-second mock-ward scenario: a nurse
  enters, works at the bedside and the equipment area (completing the seeded tasks), an unrecognized visitor
  appears, a doctor wears the wrong uniform colour, and an OT staff member enters the restricted ICU.
  Identities in this feed are **simulated**; use it to demonstrate the workflow, never as recognition accuracy.
* **CAM-01, Ward A entrance** uses your webcam (`0`) and is stopped until you press **Start camera**.

Set `SIM_SPEED=3` in `vision-worker/.env` to play the scenario faster.

## 5. Real camera demo (consented volunteers)

1. **Staff** → *Edit* a person → turn on *Written consent recorded* → *Save*.
2. **Staff** → *Enroll face* → capture 3–6 photos (front, slight turns, good light) → *Save photos*.
   The worker builds the encrypted template within seconds; the badge changes to *Enrolled*.
   If the browser cannot open the webcam, stop CAM-01 first (only one program can use it on Windows) or upload photos.
3. **Wards & cameras** → open CAM-01 → check the zones (`bedside`, `equipment`) match your mock ward.
   You can also upload an MP4 recording instead of the webcam.
4. **Tasks** → *Assign task* → e.g. *Ward inspection* in Ward A for the enrolled person.
5. **Live monitoring** → *Start camera*. Walk into view: *Identifying* → name (verified). After the
   minimum time the task becomes *Verified*; a medication delivery goes to *Needs review* for a supervisor.
6. Someone not enrolled walks in → *Unrecognized person* alert after a few seconds.
7. **Audit integrity** → *Anchor now* → *Verify integrity*.

## 6. Tamper-evidence demo

In the dashboard, **Audit integrity → Run test** applies six attacks (modification, deletion, insertion,
reordering, truncation, full rewrite) to an in-memory copy and shows that a plain hash chain misses the
full rewrite and truncation, while independent anchoring detects all six.

To tamper with the **real** log in front of examiners:

```bash
# Windows
.venv\Scripts\python scripts\tamper_demo.py modify     # or: rewrite
# macOS / Linux
.venv/bin/python scripts/tamper_demo.py modify
```

Press *Verify integrity* (it reports `HASH_MISMATCH`, or `ANCHOR_MISMATCH` for a rewrite), then restore:

```bash
.venv\Scripts\python scripts\tamper_demo.py restore
```

## 7. Tests

```bash
python run.py test
```

Runs backend tests (integrity, all six attacks, full ingestion → visit → task → alert → audit flow, role scoping),
worker tests (uniform colour with lighting correction, identity fusion, tracker, simulator) and dashboard type-check + unit tests.

## 8. How it fits together

```
Webcam / RTSP / MP4 / sim
        │
  vision-worker  ── YOLOv8 + ByteTrack → face quality gate → ArcFace/SFace open-set match
        │            → identity votes per track → HSV uniform cue → annotated JPEG frames
        │  X-Internal-Token (POST observations, frames, heartbeat; GET gallery, config)
        ▼
  FastAPI backend ── visit lifecycle · role check · task evidence engine · alerts
        │            → audit append (serialized) → Merkle batch → anchor file in data/anchors/
        ├── SQLite / PostgreSQL
        └── WebSocket /ws/monitoring ──► React dashboard (via Vite proxy)
```

Key rules implemented:

* An unmatched face stays **Unknown**; it is never assigned to the nearest staff member.
* A verified track keeps its identity through short occlusion but is dropped to *pending* (never silently swapped) after repeated contradicting matches.
* Uniform colour is only a consistency cue. A mismatch raises a review alert; identity and registered role are not changed.
* A visit is *provisional* until confirmed, ends after a timeout, and re-entry within the merge window extends the same visit.
* Task time only accumulates while the assigned person is verified in the right ward (and zone). Medication delivery always needs supervisor confirmation, which is only allowed once the visual evidence exists.
* Every meaningful change is appended to the hash chain. Verification failures are reported, never auto-repaired.

## 9. Configuration

`backend/.env`: `DATABASE_URL`, `JWT_SECRET`, `INTERNAL_TOKEN`, `EMBEDDING_KEY`, `ANCHOR_DIR`, `AUDIT_BATCH_SIZE`.
`vision-worker/.env`: `API_URL`, `INTERNAL_TOKEN` (must match), `DETECTOR`, `FACE_BACKEND`, `DEVICE`, `SIMULATE_ALL`, `SIM_SPEED`, `STREAM_FPS`.
Recognition thresholds, visit timings and the role → colour map are edited live in **Settings & health**.

**PostgreSQL:** `docker compose up -d postgres`, then set
`DATABASE_URL=postgresql+psycopg://intelliward:intelliward@localhost:5432/intelliward` in `backend/.env` and restart.
Tables are created automatically on start.

**Stronger anchoring:** point `ANCHOR_DIR` at storage the database administrator cannot write (another machine, a network share with append-only rights, or a WORM bucket). A file on the same disk demonstrates the mechanism but is not independent proof.

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found on Windows | Reinstall Python with *Add to PATH*, or use `py run.py ...` |
| Dashboard says it cannot reach the API | Make sure `python run.py backend` is running on port 8000 |
| Worker logs "Backend rejected the internal token" | `INTERNAL_TOKEN` differs between `backend/.env` and `vision-worker/.env` |
| Camera shows *Offline* | Another app is using the webcam, or the source path/URL is wrong (see Settings & health) |
| Face models missing | `.venv\Scripts\python vision-worker\setup_models.py` |
| Faces never verify | Re-enroll with clearer frontal photos; lower the SFace/ArcFace threshold slightly in Settings |
| Low FPS on CPU | Raise *Process every Nth frame* in Settings, or use a GPU |
| Start again from a clean database | `python run.py reset` |

## 11. Honest scope statement (for the report and viva)

* Figures in the IEEE paper (E1–E3) are preliminary component experiments, not results of this integrated prototype.
* The simulated feed demonstrates the workflow only. Recognition accuracy must be measured on consented
  volunteer footage using the metrics in the paper's Table II (TAR at FAR, IDF1, Visit-F1, task F1, alert latency).
* Presence near a bed is not proof of clinical care. The system records observed evidence and requires authorized confirmation for clinical completion.
* Use volunteers and a mock ward. Do not use real patient areas without institutional approval, and never use these metrics as the sole basis for disciplinary decisions.
