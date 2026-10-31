"""IntelliWard vision worker.

Pulls camera configuration from the backend, runs one processing thread per enabled camera and pushes
observations + annotated frames through the authenticated internal API. Also computes face templates
for newly enrolled staff.

Usage:
    python worker.py              # real cameras (+ simulated ones whose source is "sim")
    python worker.py --simulate   # every enabled camera uses the synthetic scenario
"""
import argparse
import base64
import logging
import os
import queue
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

from pipeline import annotate, role_classifier, simulator
from pipeline.capture import FrameSource
from pipeline.client import ApiClient
from pipeline.detector import FallbackDetector, YoloByteTrack, yolo_available
from pipeline.identity_fusion import IdentityFusion

load_dotenv(Path(__file__).resolve().parent / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("worker")

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("INTERNAL_TOKEN", "change-me-worker-token")
DETECTOR = os.getenv("DETECTOR", "auto")
FACE_BACKEND = os.getenv("FACE_BACKEND", "auto")
YOLO_WEIGHTS = os.getenv("YOLO_WEIGHTS", "yolov8n.pt")
STREAM_FPS = float(os.getenv("STREAM_FPS", "8"))
STREAM_WIDTH = int(os.getenv("STREAM_WIDTH", "960"))


def pick_device(pref: str) -> str:
    if pref in ("cpu", "cuda"):
        return pref
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


DEVICE = pick_device(os.getenv("DEVICE", "auto"))


class Poster(threading.Thread):
    """Non-blocking sender so slow HTTP never stalls inference. Drops the oldest item when full."""

    def __init__(self, api: ApiClient):
        super().__init__(daemon=True, name="poster")
        self.api = api
        self.q: queue.Queue = queue.Queue(maxsize=32)

    def put(self, kind: str, *args):
        try:
            self.q.put_nowait((kind, args))
        except queue.Full:
            try:
                self.q.get_nowait()
            except queue.Empty:
                pass
            self.q.put_nowait((kind, args))

    def run(self):
        while True:
            kind, args = self.q.get()
            if kind == "obs":
                self.api.observations(*args)
            elif kind == "frame":
                self.api.frame(*args)


def encode(frame: np.ndarray) -> bytes:
    h, w = frame.shape[:2]
    if w > STREAM_WIDTH:
        frame = cv2.resize(frame, (STREAM_WIDTH, int(h * STREAM_WIDTH / w)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
    return buf.tobytes() if ok else b""


class Shared:
    """State shared across camera threads."""

    def __init__(self):
        self.settings: dict = {}
        self.staff: dict[int, dict] = {}
        self.face = None
        self.gallery = None
        self.lock = threading.Lock()


class CameraThread(threading.Thread):
    def __init__(self, cam: dict, shared: Shared, poster: Poster, simulate: bool):
        super().__init__(daemon=True, name=f"cam-{cam['code']}")
        self.cam = cam
        self.shared = shared
        self.poster = poster
        self.simulate = simulate or cam["source"].strip().lower() == "sim"
        self.stop_event = threading.Event()
        self.fps = 0.0
        self.latency_ms = 0.0
        self.error: str | None = None
        self.mode = "simulator" if self.simulate else ""

    def stop(self):
        self.stop_event.set()

    def status(self) -> dict:
        return {"fps": round(self.fps, 1), "latency_ms": round(self.latency_ms, 1), "error": self.error,
                "mode": self.mode}

    def run(self):
        try:
            self._run_sim() if self.simulate else self._run_real()
        except Exception as exc:
            self.error = str(exc)
            log.exception("[%s] camera thread crashed", self.cam["code"])

    # ------------------------------------------------------------------ simulated feed
    def _run_sim(self):
        code = self.cam["code"]
        scen = simulator.Scenario(self.cam, list(self.shared.staff.values()),
                                  self.shared.settings.get("role_color_map", {}))
        seen: set[str] = set()
        last_obs = last_frame = 0.0
        t_prev = time.time()
        while not self.stop_event.is_set():
            now = time.time()
            people = scen.state(now)
            alive = {p["track_id"] for p in people}
            if now - last_obs >= 0.5:
                tracks = []
                for p in people:
                    staff = p["actor"]["staff"]
                    tracks.append({"track_id": p["track_id"], "bbox": [round(v, 4) for v in p["box"]],
                                   "identity_status": p["status"],
                                   "staff_id": staff["id"] if staff and p["status"] == "verified" else None,
                                   "similarity": 0.9 if staff else 0.12, "role_color": p["actor"]["color"],
                                   "role_color_conf": 0.95, "det_conf": 0.9, "model_version": "simulator"})
                self.poster.put("obs", {"camera_id": code, "fps": round(self.fps, 1), "tracks": tracks,
                                        "lost_tracks": sorted(seen - alive)})
                seen = alive
                last_obs = now
            if now - last_frame >= 1 / max(STREAM_FPS, 1):
                img = simulator.render(self.cam, people)
                H, W = img.shape[:2]
                draw = []
                for p in people:
                    x1, y1, x2, y2 = p["box"]
                    st = p["actor"]["staff"]
                    label = (f"{st['staff_code']} {st['name'].split()[-1]}" if st and p["status"] == "verified"
                             else "Unknown" if p["status"] == "unknown" else "Identifying")
                    draw.append({"px": (x1 * W, y1 * H, x2 * W, y2 * H), "identity_status": p["status"],
                                 "label": label})
                annotate.draw(img, draw, self.cam.get("zones", []), f"{code}  simulated feed")
                self.poster.put("frame", code, encode(img))
                last_frame = now
            dt = time.time() - t_prev
            t_prev = time.time()
            self.fps = 0.9 * self.fps + 0.1 * (1 / dt if dt > 0 else 0)
            self.stop_event.wait(0.1)

    # ------------------------------------------------------------------ real camera
    def _run_real(self):
        code = self.cam["code"]
        cfg = self.shared.settings
        src = FrameSource(code, self.cam["source"])
        src.start()
        use_yolo = DETECTOR == "yolo" or (DETECTOR == "auto" and yolo_available())
        if use_yolo:
            det = YoloByteTrack(YOLO_WEIGHTS, DEVICE, float(cfg.get("detector_confidence", 0.45)))
        else:
            det = FallbackDetector(float(cfg.get("detector_confidence", 0.45)))
        face = self.shared.face
        self.mode = f"{det.name} | {face.model_version if face else 'no face model'} | {DEVICE}"
        log.info("[%s] pipeline: %s", code, self.mode)
        fusion = IdentityFusion()
        last_seq = frame_idx = 0
        last_obs = last_frame = 0.0
        latest_tracks: list[dict] = []
        try:
            while not self.stop_event.is_set():
                self.error = src.error
                seq, frame, ts = src.latest()
                if frame is None or seq == last_seq:
                    self.stop_event.wait(0.01)
                    continue
                last_seq = seq
                frame_idx += 1
                stride = max(1, int(self.shared.settings.get("frame_stride", 2)))
                if frame_idx % stride:
                    continue
                t0 = time.time()
                frame = frame.copy()
                H, W = frame.shape[:2]
                settings = self.shared.settings
                min_face = int(settings.get("face_min_size", 48))
                faces = face.detect(frame, True, min_face) if face is not None else []
                tracks = det.update(frame, faces)
                gallery = self.shared.gallery
                thr_key = face.default_threshold_key if face else "face_match_threshold"
                threshold = float(settings.get(thr_key, 0.42))
                votes_needed = int(settings.get("identity_votes_required", 2))
                gains = role_classifier.frame_gains(frame)
                out, draw, alive = [], [], set()
                for tid, x1, y1, x2, y2, conf in tracks:
                    key = f"{code}-{tid}"
                    alive.add(key)
                    ident = fusion.get(key)
                    f = _face_for_box(faces, (x1, y1, x2, y2))
                    if f is not None and f.embedding is not None and gallery is not None:
                        if ident.status != "verified" or frame_idx - ident.last_face_frame > 10:
                            sid, sim = gallery.match(f.embedding, threshold)
                            ident.add_vote(sid, sim, votes_needed)
                            ident.last_face_frame = frame_idx
                    color, cconf = role_classifier.classify(role_classifier.torso_crop(frame, (x1, y1, x2, y2)), gains)
                    ident.role_color, ident.role_conf = color, cconf
                    bbox = [round(max(0, x1) / W, 4), round(max(0, y1) / H, 4), round(min(W, x2) / W, 4),
                            round(min(H, y2) / H, 4)]
                    out.append({"track_id": key, "bbox": bbox, "identity_status": ident.status,
                                "staff_id": ident.staff_id if ident.status == "verified" else None,
                                "similarity": round(ident.similarity, 4), "role_color": color,
                                "role_color_conf": cconf, "det_conf": round(conf, 3),
                                "model_version": face.model_version if face else "none"})
                    meta = gallery.meta.get(ident.staff_id, {}) if gallery and ident.staff_id else {}
                    label = (f"{meta.get('staff_code', '')} {meta.get('name', '').split(' ')[-1]}".strip()
                             if ident.status == "verified" else "Unknown" if ident.status == "unknown"
                             else "Identifying")
                    draw.append({"px": (x1, y1, x2, y2), "identity_status": ident.status, "label": label})
                lost = fusion.prune(alive)
                latest_tracks = out
                self.latency_ms = 0.8 * self.latency_ms + 0.2 * (time.time() - t0) * 1000
                now = time.time()
                if now - last_obs >= 0.5 or lost:
                    self.poster.put("obs", {"camera_id": code, "fps": round(self.fps, 1), "tracks": latest_tracks,
                                            "lost_tracks": lost, "frame_ts": ts.isoformat() if ts else None})
                    last_obs = now
                if now - last_frame >= 1 / max(STREAM_FPS, 1):
                    annotate.draw(frame, draw, self.cam.get("zones", []),
                                  f"{code}  {det.name}  {self.latency_ms:.0f} ms")
                    self.poster.put("frame", code, encode(frame))
                    last_frame = now
                self.fps = 0.9 * self.fps + 0.1 * (1000 / max(self.latency_ms, 1) if self.latency_ms else 0)
        finally:
            src.stop()


def _face_for_box(faces, box):
    """The largest face whose centre lies in the upper half of the person box."""
    x1, y1, x2, y2 = box
    best, best_area = None, 0
    for f in faces:
        fx = (f.box[0] + f.box[2]) / 2
        fy = (f.box[1] + f.box[3]) / 2
        if x1 <= fx <= x2 and y1 <= fy <= y1 + 0.5 * (y2 - y1):
            area = (f.box[2] - f.box[0]) * (f.box[3] - f.box[1])
            if area > best_area:
                best, best_area = f, area
    return best


def enrollment_loop(api: ApiClient, shared: Shared, stop: threading.Event):
    from pipeline.face_recognizer import Gallery
    last_gallery = 0.0
    while not stop.is_set():
        face = shared.face
        if face is not None:
            pending = api.pending_enrollment(face.model_version) or {}
            changed = False
            for sid in pending.get("staff_ids", []):
                data = api.enrollment_images(sid) or {}
                imgs = []
                for b64 in data.get("images", []):
                    arr = np.frombuffer(base64.b64decode(b64), np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is not None:
                        imgs.append(img)
                vec, used, rejected = face.enrollment_template(imgs)
                api.save_embedding(sid, {"model_version": face.model_version, "vector": vec or [],
                                         "num_images": used, "rejected_images": rejected})
                log.info("Enrollment for staff %s: %d usable, %d rejected images", sid, used, rejected)
                changed = True
            if changed or time.time() - last_gallery > 10:
                g = api.gallery(face.model_version)
                if g is not None:
                    gal = Gallery()
                    gal.load(g.get("entries", []))
                    shared.gallery = gal
                    last_gallery = time.time()
        stop.wait(4)


def main():
    parser = argparse.ArgumentParser(description="IntelliWard vision worker")
    parser.add_argument("--simulate", action="store_true", help="use the synthetic scenario for every camera")
    args = parser.parse_args()
    simulate_all = args.simulate or os.getenv("SIMULATE_ALL", "false").lower() == "true"

    api = ApiClient(API_URL, TOKEN)
    shared = Shared()
    poster = Poster(api)
    poster.start()
    stop = threading.Event()

    if not simulate_all:
        try:
            from pipeline.face_recognizer import FaceEngine
            shared.face = FaceEngine(FACE_BACKEND, DEVICE)
        except Exception as exc:
            log.warning("Face recognition disabled: %s", exc)
    threading.Thread(target=enrollment_loop, args=(api, shared, stop), daemon=True, name="enroll").start()

    detector_name = ("yolov8+bytetrack" if (DETECTOR == "yolo" or (DETECTOR == "auto" and yolo_available()))
                     else "fallback(face-anchored/hog)+iou")
    log.info("Worker started. API=%s detector=%s device=%s simulate_all=%s", API_URL, detector_name, DEVICE,
             simulate_all)
    threads: dict[str, CameraThread] = {}
    last_hb = 0.0
    while True:
        try:
            cfg = api.config()
            if cfg:
                shared.settings = cfg["settings"]
                shared.staff = {s["id"]: s for s in cfg["staff"]}
                wanted = {c["code"]: c for c in cfg["cameras"] if c["enabled"]}
                for code in list(threads):
                    t = threads[code]
                    c = wanted.get(code)
                    if c is None or c["source"] != t.cam["source"] or not t.is_alive():
                        t.stop()
                        t.join(timeout=3)
                        del threads[code]
                    elif c["zones"] != t.cam.get("zones"):
                        t.cam["zones"] = c["zones"]
                for code, c in wanted.items():
                    if code not in threads:
                        t = CameraThread(c, shared, poster, simulate_all)
                        t.start()
                        threads[code] = t
                        log.info("Started camera %s (%s)", code, "simulated" if t.simulate else c["source"])
            if time.time() - last_hb > 5:
                api.heartbeat({"worker_id": "vision-worker", "detector": detector_name, "tracker":
                               "bytetrack" if "bytetrack" in detector_name else "iou",
                               "face_model": shared.face.model_version if shared.face else "none",
                               "device": DEVICE, "cameras": {k: t.status() for k, t in threads.items()},
                               "latency_ms": max([t.latency_ms for t in threads.values()] or [0])})
                last_hb = time.time()
            time.sleep(3)
        except KeyboardInterrupt:
            log.info("Stopping worker")
            stop.set()
            for t in threads.values():
                t.stop()
            break


if __name__ == "__main__":
    main()
