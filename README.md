<div align="center">

<img src="assets/banner.svg" alt="IntelliWard: AI-powered hospital staff monitoring with tamper-evident audit logging" width="100%"/>

<br/><br/>

<img src="https://img.shields.io/badge/Python-3.10%20%E2%80%93%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
<img src="https://img.shields.io/badge/Node.js-18%2B-339933?style=for-the-badge&logo=nodedotjs&logoColor=white" alt="Node.js"/>
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
<img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React"/>
<img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript"/>
<img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite"/>
<br/>
<img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind CSS"/>
<img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" alt="OpenCV"/>
<img src="https://img.shields.io/badge/YOLOv8-Ultralytics-111F68?style=for-the-badge&logo=yolo&logoColor=white" alt="YOLOv8"/>
<img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch"/>
<img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite"/>
<img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
<img src="https://img.shields.io/badge/JWT-000000?style=for-the-badge&logo=jsonwebtokens&logoColor=white" alt="JWT"/>

<br/><br/>

<img src="https://img.shields.io/github/last-commit/LoganthP/Intelliward?style=flat-square&color=38bdf8" alt="Last commit"/>
<img src="https://img.shields.io/github/stars/LoganthP/Intelliward?style=flat-square&color=5eead4" alt="Stars"/>
<img src="https://img.shields.io/github/languages/top/LoganthP/Intelliward?style=flat-square&color=818cf8" alt="Top language"/>
<img src="https://img.shields.io/badge/status-final--year%20prototype-0ea5e9?style=flat-square" alt="Status"/>

<br/><br/>

**Camera observation → verified identity → role & ward → visit → task evidence → audit trail → live dashboard**

<sub>Final-year CSE major project · Vidyavardhaka College of Engineering, Mysuru</sub>

<br/>

[Overview](#-overview) · [Features](#-highlights) · [Tech Stack](#-tech-stack) · [Architecture](#-architecture) · [Quick Start](#-quick-start) · [Demo](#-demo-walkthrough) · [Tamper Evidence](#-tamper-evident-audit-trail) · [Troubleshooting](#-troubleshooting)

</div>

<img src="assets/divider.svg" width="100%" alt=""/>

## 🩺 Overview

**IntelliWard** is a working prototype of an AI-assisted ward monitoring system. It watches a camera feed, works out *who* is in view and *where*, decides whether the right person did the assigned task in the right place for long enough, and records every meaningful step in an audit log that **detects tampering**, including full rewrites by someone with database access.

It is deliberately an **evidence system, not a judge**: an unmatched face stays *Unknown*, uniform colour is only a consistency cue, and clinical completion always needs an authorized human to confirm.

<div align="center">
<img src="assets/pipeline.svg" alt="IntelliWard pipeline from camera to dashboard" width="100%"/>
</div>

<img src="assets/divider.svg" width="100%" alt=""/>

## ✨ Highlights

| | Capability | What it does |
|---|---|---|
| 🎥 | **Multi-source vision** | Webcam, RTSP, uploaded MP4, or a built-in simulator |
| 🧍 | **Person tracking** | YOLOv8 + ByteTrack keep a stable track per person |
| 🪪 | **Open-set face identity** | RetinaFace + ArcFace (InsightFace) or YuNet + SFace (OpenCV); unmatched faces stay **Unknown** |
| 👕 | **Uniform consistency cue** | HSV colour check against the role → colour map; a mismatch raises a *review alert*, never changes identity or role |
| 🏥 | **Visit lifecycle** | Provisional → confirmed visits, timeout end, and re-entry merge window |
| ✅ | **Task evidence engine** | Time only counts while the assigned person is verified in the right ward (and zone); medication delivery always needs supervisor confirmation |
| 🚨 | **Alerts** | Unrecognized person, wrong uniform colour, restricted-ward entry |
| 🔗 | **Tamper-evident audit** | SHA-256 hash chain + Merkle batches + independent append-only anchors |
| 📡 | **Live dashboard** | React dashboard fed over WebSocket, with role-scoped views (admin / supervisor / staff) |
| 🔐 | **Privacy by design** | Written-consent flag per person, encrypted face templates, volunteer-only demo footage |

<img src="assets/divider.svg" width="100%" alt=""/>

## 🧰 Tech Stack

<div align="center">

| Layer | Technology | Folder |
|:---|:---|:---|
| 🖥️ **Dashboard** | React 18 · TypeScript · Vite · Tailwind CSS · Framer Motion · Recharts | `frontend/` |
| ⚙️ **API** | Python · FastAPI · SQLAlchemy · WebSockets · JWT | `backend/` |
| 👁️ **Vision worker** | OpenCV · YOLOv8 + ByteTrack (Ultralytics) · RetinaFace + ArcFace (InsightFace) *or* YuNet + SFace (OpenCV) · HSV uniform cue | `vision-worker/` |
| 🔗 **Integrity** | SHA-256 hash chain · Merkle batches · independent append-only anchors | `backend/app/integrity/` |
| 🗄️ **Database** | SQLite (zero setup, default) · PostgreSQL via `docker-compose.yml` | `data/` |
| 🧪 **Tooling** | `run.py` orchestrator · pytest-style backend/worker tests · dashboard type-check + unit tests | `run.py`, `scripts/` |

</div>

<img src="assets/divider.svg" width="100%" alt=""/>

## 🏗️ Architecture

### System overview

```mermaid
flowchart LR
    subgraph SRC["Video sources"]
        direction TB
        S1["Webcam"]
        S2["RTSP stream"]
        S3["MP4 file"]
        S4["Simulator"]
    end

    subgraph VW["vision-worker"]
        direction TB
        V1["YOLOv8 + ByteTrack<br/>person tracking"]
        V2["Face quality gate"]
        V3["ArcFace / SFace<br/>open-set match"]
        V4["Identity votes<br/>per track"]
        V5["HSV uniform cue"]
        V1 --> V2 --> V3 --> V4 --> V5
    end

    subgraph API["FastAPI backend"]
        direction TB
        A1["Visit lifecycle"]
        A2["Role & ward check"]
        A3["Task evidence engine"]
        A4["Alerts"]
        A5["Audit append<br/>(serialized)"]
        A1 --> A2 --> A3
        A3 --> A4
        A3 --> A5
        A4 --> A5
    end

    DB[("SQLite / PostgreSQL")]
    ANC["Anchor files<br/>data/anchors/"]
    UI["React dashboard"]

    SRC --> VW
    VW -- "X-Internal-Token<br/>observations, frames, heartbeat" --> API
    API -- "gallery, config" --> VW
    API --> DB
    A5 --> ANC
    API -- "WebSocket /ws/monitoring" --> UI

    classDef src fill:#0b2a40,stroke:#38bdf8,color:#e2e8f0
    classDef worker fill:#10243a,stroke:#5eead4,color:#e2e8f0
    classDef api fill:#16213e,stroke:#818cf8,color:#e2e8f0
    class S1,S2,S3,S4 src
    class V1,V2,V3,V4,V5 worker
    class A1,A2,A3,A4,A5 api
```

### One observation, end to end

```mermaid
sequenceDiagram
    autonumber
    participant Cam as Camera
    participant VW as Vision worker
    participant API as FastAPI backend
    participant Aud as Audit chain
    participant UI as Dashboard
    participant Sup as Supervisor

    Cam->>VW: video frames
    VW->>VW: detect, track, match face, uniform cue
    VW->>API: POST observation (X-Internal-Token)
    API->>API: update visit, check role and ward, update task evidence
    API->>Aud: append event to hash chain
    API-->>UI: push update over WebSocket
    Note over API,UI: Unknown faces and wrong uniforms raise alerts
    Sup->>UI: review medication delivery
    UI->>API: confirm (only allowed once visual evidence exists)
    API->>Aud: append confirmation
    API-->>UI: task marked confirmed
```

<img src="assets/divider.svg" width="100%" alt=""/>

## 🧠 How Verification Works

### Identity: never guess

```mermaid
flowchart TD
    F["Face crop on a tracked person"] --> Q{"Quality gate passed?"}
    Q -- "no" --> P["Stay pending"]
    Q -- "yes" --> M{"Open-set match<br/>above threshold?"}
    M -- "no" --> U["Unknown<br/>(never assigned to the nearest staff member)"]
    U --> AL["Unrecognized person alert<br/>after a few seconds"]
    M -- "yes" --> VO["Add identity vote to the track"]
    VO --> C{"Enough consistent votes?"}
    C -- "no" --> P
    C -- "yes" --> OK["Verified identity"]
    OK --> X{"Repeated contradicting<br/>matches?"}
    X -- "yes" --> P
    X -- "no" --> OK

    classDef good fill:#0b2a2a,stroke:#5eead4,color:#e2e8f0
    classDef warn fill:#3a1d1d,stroke:#f87171,color:#fee2e2
    class OK good
    class U,AL warn
```

A verified track keeps its identity through short occlusion but drops back to *pending* (never silently swapped) after repeated contradicting matches.

### Visit lifecycle

```mermaid
stateDiagram-v2
    [*] --> Provisional: verified person seen in a ward
    Provisional --> Confirmed: visit confirmed
    Provisional --> Ended: timeout
    Confirmed --> Ended: timeout
    Ended --> [*]
    note right of Ended
        Re-entry within the merge window
        extends the same visit
    end note
```

### Task evidence

```mermaid
stateDiagram-v2
    [*] --> Assigned
    Assigned --> Accumulating: assigned person verified in the right ward and zone
    Accumulating --> Accumulating: time keeps adding up
    Accumulating --> Verified: minimum time reached
    Accumulating --> NeedsReview: medication delivery
    NeedsReview --> Confirmed: supervisor confirms (visual evidence required)
    Verified --> [*]
    Confirmed --> [*]
```

<img src="assets/divider.svg" width="100%" alt=""/>

## 🔗 Tamper-Evident Audit Trail

Every meaningful change is appended to a **SHA-256 hash chain**, grouped into **Merkle batches**, and each batch root is written to an **independent append-only anchor**. Verification failures are *reported, never auto-repaired*.

```mermaid
flowchart LR
    E["Meaningful event"] --> H["Hash entry together<br/>with previous hash<br/>(SHA-256)"]
    H --> CH[("Hash chain")]
    CH --> B["Merkle batch<br/>every AUDIT_BATCH_SIZE entries"]
    B --> R["Merkle root"]
    R --> A["Anchor file<br/>in ANCHOR_DIR"]

    CH --> V{"Verify integrity"}
    A --> V
    V -- "chain links broken" --> X1["HASH_MISMATCH"]
    V -- "root differs from anchor" --> X2["ANCHOR_MISMATCH"]
    V -- "all consistent" --> OK["Verified"]

    classDef good fill:#0b2a2a,stroke:#5eead4,color:#e2e8f0
    classDef bad fill:#3a1d1d,stroke:#f87171,color:#fee2e2
    class OK good
    class X1,X2 bad
```

### Why anchoring matters

The built-in test (**Audit integrity → Run test**) applies six attacks to an in-memory copy of the log:

| Attack | Plain hash chain | Hash chain + independent anchors |
|:---|:---:|:---:|
| Modification | ✅ detected | ✅ detected |
| Deletion | ✅ detected | ✅ detected |
| Insertion | ✅ detected | ✅ detected |
| Reordering | ✅ detected | ✅ detected |
| Truncation | ❌ missed | ✅ detected |
| Full rewrite | ❌ missed | ✅ detected |

<img src="assets/divider.svg" width="100%" alt=""/>

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Check |
|:---|:---|:---|
| Python | 3.10, 3.11 or 3.12 (3.11 recommended) | `python --version` |
| Node.js | 18 or newer (20 LTS recommended) | `node --version` |
| OS | Windows 11, macOS or Linux | |
| GPU | Optional | |
| Internet | First run only (packages and model downloads) | |

> **Windows:** when installing Python, tick **"Add python.exe to PATH"**.

### 1. Clone and install (one command)

```bash
git clone https://github.com/LoganthP/Intelliward.git
cd Intelliward
python run.py setup --ai
```

This creates `.venv`, installs the backend, the vision worker (YOLOv8 + ByteTrack) and the dashboard packages, writes `backend/.env` and `vision-worker/.env` with matching random secrets, and downloads the OpenCV face models.

<details>
<summary><b>Other install options</b></summary>

<br/>

| Goal | Command |
|:---|:---|
| Faster install **without PyTorch** (simulated cameras and OpenCV face recognition still work; real cameras use the fallback detector) | `python run.py setup` |
| Add **InsightFace** (RetinaFace + ArcFace) | `python run.py setup --ai --insightface` |
| **NVIDIA GPU** | After setup, install the CUDA build of PyTorch into `.venv` using the selector at [pytorch.org](https://pytorch.org). The worker detects CUDA automatically (`DEVICE=auto`). |

On Windows, InsightFace needs *Microsoft C++ Build Tools*. If it fails nothing breaks: the worker falls back to YuNet + SFace.

</details>

### 2. Run everything

```bash
python run.py dev
```

| Service | Address |
|:---|:---|
| 🖥️ Dashboard | http://localhost:5173 |
| ⚙️ API | http://localhost:8000 |
| 📖 API docs (Swagger) | http://localhost:8000/docs |

`Ctrl+C` stops all three services. To run them separately (three terminals):

```bash
python run.py backend
python run.py worker          # add --simulate to force every camera into the synthetic scenario
python run.py frontend
```

### 3. Sign in

| Username | Password | Can do |
|:---|:---|:---|
| `admin` | `admin123` | Everything, including settings, cameras and the tamper test |
| `supervisor` | `super123` | Staff, tasks, reviews, alerts, audit verification |
| `nurse1` | `staff123` | Sees only their own tasks and visits |

> ⚠️ These are demo credentials. **Change them before showing the system to anyone outside the team.**

### `run.py` command reference

| Command | Purpose |
|:---|:---|
| `python run.py setup [--ai] [--insightface]` | Create `.venv`, install everything, generate `.env` files, download face models |
| `python run.py dev` | Start backend, worker and dashboard together |
| `python run.py backend` | FastAPI server only (port 8000) |
| `python run.py worker [--simulate]` | Vision worker only |
| `python run.py frontend` | Vite dashboard only (port 5173) |
| `python run.py test` | Run backend, worker and dashboard tests |
| `python run.py reset` | Start again from a clean database |

<img src="assets/divider.svg" width="100%" alt=""/>

## 🎬 Demo Walkthrough

### What you see on first start

The database seeds **three wards** (Ward A, ICU *restricted*, OT-1 *restricted*), **four staff members**, demo tasks and **two cameras**:

| Camera | Source | Behaviour |
|:---|:---|:---|
| **CAM-02** · ICU simulated feed | Built-in simulator | Starts automatically and plays a **150-second mock-ward scenario**: a nurse enters, works at the bedside and equipment area (completing seeded tasks), an unrecognized visitor appears, a doctor wears the wrong uniform colour, and an OT staff member enters the restricted ICU |
| **CAM-01** · Ward A entrance | Your webcam (`0`) | Stopped until you press **Start camera** |

> Identities in the simulated feed are **simulated**. Use it to demonstrate the workflow, never as recognition accuracy. Set `SIM_SPEED=3` in `vision-worker/.env` to play it faster.

### Real camera demo (consented volunteers)

1. **Staff** → *Edit* a person → turn on *Written consent recorded* → *Save*.
2. **Staff** → *Enroll face* → capture 3–6 photos (front, slight turns, good light) → *Save photos*. The worker builds the encrypted template within seconds and the badge changes to *Enrolled*.
   If the browser cannot open the webcam, stop CAM-01 first (only one program can use it on Windows) or upload photos instead.
3. **Wards & cameras** → open CAM-01 → check the zones (`bedside`, `equipment`) match your mock ward. You can also upload an MP4 recording instead of using the webcam.
4. **Tasks** → *Assign task*, e.g. *Ward inspection* in Ward A for the enrolled person.
5. **Live monitoring** → *Start camera*. Walk into view: *Identifying* → name (verified). After the minimum time the task becomes **Verified**; a medication delivery goes to **Needs review** for a supervisor.
6. Have someone who is not enrolled walk in → an *Unrecognized person* alert appears after a few seconds.
7. **Audit integrity** → *Anchor now* → *Verify integrity*.

<img src="assets/divider.svg" width="100%" alt=""/>

## 🧪 Tamper-Evidence Demo

**In the dashboard:** *Audit integrity → Run test* runs all six attacks on an in-memory copy.

**On the real log, in front of examiners:**

```bash
# Windows
.venv\Scripts\python scripts\tamper_demo.py modify      # or: rewrite

# macOS / Linux
.venv/bin/python scripts/tamper_demo.py modify
```

Press **Verify integrity**. It reports `HASH_MISMATCH` (or `ANCHOR_MISMATCH` for a rewrite). Then restore the log:

```bash
.venv\Scripts\python scripts\tamper_demo.py restore
```

<img src="assets/divider.svg" width="100%" alt=""/>

## ✅ Tests

```bash
python run.py test
```

| Suite | Covers |
|:---|:---|
| **Backend** | Integrity, all six attacks, full ingestion → visit → task → alert → audit flow, role scoping |
| **Vision worker** | Uniform colour with lighting correction, identity fusion, tracker, simulator |
| **Dashboard** | Type-check and unit tests |

<img src="assets/divider.svg" width="100%" alt=""/>

## ⚙️ Configuration

| File | Keys |
|:---|:---|
| `backend/.env` | `DATABASE_URL` · `JWT_SECRET` · `INTERNAL_TOKEN` · `EMBEDDING_KEY` · `ANCHOR_DIR` · `AUDIT_BATCH_SIZE` |
| `vision-worker/.env` | `API_URL` · `INTERNAL_TOKEN` (**must match the backend**) · `DETECTOR` · `FACE_BACKEND` · `DEVICE` · `SIMULATE_ALL` · `SIM_SPEED` · `STREAM_FPS` |

Recognition thresholds, visit timings and the role → colour map are edited live in **Settings & health** inside the dashboard.

### Switch to PostgreSQL

```bash
docker compose up -d postgres
```

Then set this in `backend/.env` and restart. Tables are created automatically on start.

```env
DATABASE_URL=postgresql+psycopg://intelliward:intelliward@localhost:5432/intelliward
```

### Stronger anchoring

Point `ANCHOR_DIR` at storage the database administrator **cannot write**: another machine, a network share with append-only rights, or a WORM bucket. A file on the same disk demonstrates the mechanism but is **not** independent proof.

<img src="assets/divider.svg" width="100%" alt=""/>

## 📁 Project Structure

```text
Intelliward/
├── backend/                 # FastAPI app (SQLAlchemy, WebSockets, JWT)
│   └── app/
│       └── integrity/       # hash chain, Merkle batches, anchors
├── frontend/                # React 18 + TypeScript + Vite dashboard
├── vision-worker/           # tracking, face match, uniform cue, simulator
│   └── setup_models.py      # downloads the OpenCV face models
├── shared/
│   └── contracts/           # shared API / data contracts
├── scripts/
│   └── tamper_demo.py       # modify | rewrite | restore the real audit log
├── docker-compose.yml       # optional PostgreSQL
├── run.py                   # setup · dev · backend · worker · frontend · test · reset
└── data/                    # generated at runtime: SQLite DB and anchors/
```

<img src="assets/divider.svg" width="100%" alt=""/>

## 🛠️ Troubleshooting

<details>
<summary><b>Click to expand the fix table</b></summary>

<br/>

| Problem | Fix |
|:---|:---|
| `python` not found on Windows | Reinstall Python with *Add to PATH*, or use `py run.py ...` |
| Dashboard says it cannot reach the API | Make sure `python run.py backend` is running on port 8000 |
| Worker logs *"Backend rejected the internal token"* | `INTERNAL_TOKEN` differs between `backend/.env` and `vision-worker/.env` |
| Camera shows *Offline* | Another app is using the webcam, or the source path / URL is wrong (see *Settings & health*) |
| Face models missing | `.venv\Scripts\python vision-worker\setup_models.py` |
| Faces never verify | Re-enroll with clearer frontal photos; lower the SFace / ArcFace threshold slightly in Settings |
| Low FPS on CPU | Raise *Process every Nth frame* in Settings, or use a GPU |
| Start again from a clean database | `python run.py reset` |

</details>

<img src="assets/divider.svg" width="100%" alt=""/>

## ⚖️ Scope & Responsible Use

This is a prototype, and the numbers should be read that way.

- Figures in the IEEE paper (E1–E3) are **preliminary component experiments**, not results of this integrated prototype.
- The simulated feed demonstrates the **workflow only**. Recognition accuracy must be measured on consented volunteer footage using the paper's Table II metrics (TAR at FAR, IDF1, Visit-F1, task F1, alert latency).
- Presence near a bed is **not proof of clinical care**. The system records observed evidence and requires authorized confirmation for clinical completion.
- Use volunteers and a mock ward. **Do not use real patient areas without institutional approval**, and never use these metrics as the sole basis for disciplinary decisions.

<img src="assets/divider.svg" width="100%" alt=""/>

## 👥 Team

| Name | Role |
|:---|:---|
| **Loganth P** ([@LoganthP](https://github.com/LoganthP)) | Team member |
| **Harshith Gowda K** | Team member |
| **Mahesh** | Team member |
| **Dr. Janhavi V** | Project guide, Dept. of CSE |

Department of Computer Science & Engineering, **Vidyavardhaka College of Engineering, Mysuru**.

## 📄 License

Academic major-project prototype. All rights reserved by the authors unless a `LICENSE` file in this repository states otherwise.

<div align="center">

<img src="assets/divider.svg" width="100%" alt=""/>

<sub>Built to make ward activity **verifiable**, not just visible. ⭐ Star the repo if you found it useful.</sub>

</div>
