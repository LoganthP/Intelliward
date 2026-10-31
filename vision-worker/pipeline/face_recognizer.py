"""Face localization + embedding with open-set matching and quality gates.

Backends:
  insightface : RetinaFace detector + ArcFace (buffalo_l)       model_version "insightface-buffalo_l"
  opencv      : YuNet detector + SFace recognizer (OpenCV zoo)   model_version "opencv-yunet-sface-2021dec"
"""
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger("worker.face")
MODELS = Path(__file__).resolve().parents[1] / "models"
YUNET = MODELS / "face_detection_yunet_2023mar.onnx"
SFACE = MODELS / "face_recognition_sface_2021dec.onnx"


@dataclass
class Face:
    box: tuple[float, float, float, float]   # x1,y1,x2,y2 pixels
    score: float
    landmarks: np.ndarray | None             # 5x2 (eyes, nose, mouth corners)
    embedding: np.ndarray | None = None      # L2-normalized
    quality_ok: bool = False
    quality_reason: str = ""


def _l2(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.float32).ravel()
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def assess_quality(img: np.ndarray, face: Face, min_size: int) -> tuple[bool, str]:
    x1, y1, x2, y2 = [int(v) for v in face.box]
    w, h = x2 - x1, y2 - y1
    if min(w, h) < min_size:
        return False, "face too small"
    crop = img[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
    if crop.size == 0:
        return False, "empty crop"
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if cv2.Laplacian(gray, cv2.CV_64F).var() < 25:
        return False, "too blurred"
    if face.landmarks is not None and len(face.landmarks) >= 3:
        le, re, nose = face.landmarks[0], face.landmarks[1], face.landmarks[2]
        eye_dist = abs(re[0] - le[0])
        if eye_dist < 1:
            return False, "pose"
        if abs(nose[0] - (le[0] + re[0]) / 2) / eye_dist > 0.45:
            return False, "head turned"
    return True, ""


class FaceEngine:
    def __init__(self, backend: str = "auto", device: str = "cpu"):
        self.backend = None
        self.model_version = ""
        if backend in ("auto", "insightface"):
            try:
                from insightface.app import FaceAnalysis
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if device == "cuda" else ["CPUExecutionProvider"]
                self.app = FaceAnalysis(name="buffalo_l", allowed_modules=["detection", "recognition"], providers=providers)
                self.app.prepare(ctx_id=0 if device == "cuda" else -1, det_size=(640, 640))
                self.backend = "insightface"
                self.model_version = "insightface-buffalo_l"
            except Exception as exc:
                if backend == "insightface":
                    raise
                log.info("InsightFace unavailable (%s); using OpenCV YuNet + SFace", exc.__class__.__name__)
        if self.backend is None:
            if not YUNET.exists() or not SFACE.exists():
                raise FileNotFoundError("OpenCV face models missing. Run: python setup_models.py")
            self.det = cv2.FaceDetectorYN.create(str(YUNET), "", (320, 320), 0.75, 0.3, 5000)
            self.rec = cv2.FaceRecognizerSF.create(str(SFACE), "")
            self.backend = "opencv"
            self.model_version = "opencv-yunet-sface-2021dec"
        log.info("Face engine: %s", self.model_version)

    @property
    def default_threshold_key(self) -> str:
        return "face_match_threshold" if self.backend == "insightface" else "face_match_threshold_sface"

    def detect(self, img: np.ndarray, with_embeddings: bool = True, min_size: int = 48) -> list[Face]:
        faces: list[Face] = []
        if self.backend == "insightface":
            for f in self.app.get(img):
                face = Face(tuple(map(float, f.bbox)), float(f.det_score),
                            np.asarray(f.kps) if getattr(f, "kps", None) is not None else None)
                face.quality_ok, face.quality_reason = assess_quality(img, face, min_size)
                if with_embeddings and face.quality_ok and getattr(f, "normed_embedding", None) is not None:
                    face.embedding = _l2(f.normed_embedding)
                faces.append(face)
            return faces
        h, w = img.shape[:2]
        self.det.setInputSize((w, h))
        _, rows = self.det.detect(img)
        if rows is None:
            return faces
        for row in rows:
            x, y, fw, fh = row[:4]
            face = Face((float(x), float(y), float(x + fw), float(y + fh)), float(row[14]),
                        row[4:14].reshape(5, 2))
            face.quality_ok, face.quality_reason = assess_quality(img, face, min_size)
            if with_embeddings and face.quality_ok:
                aligned = self.rec.alignCrop(img, row)
                face.embedding = _l2(self.rec.feature(aligned))
            faces.append(face)
        return faces

    def enrollment_template(self, images: list[np.ndarray], min_size: int = 40) -> tuple[list[float] | None, int, int]:
        """Mean of normalized embeddings over images with exactly one usable face."""
        vecs, rejected = [], 0
        for img in images:
            faces = [f for f in self.detect(img, True, min_size) if f.embedding is not None]
            if len(faces) != 1:
                rejected += 1
                continue
            vecs.append(faces[0].embedding)
        if not vecs:
            return None, 0, rejected
        return _l2(np.mean(vecs, axis=0)).tolist(), len(vecs), rejected


class Gallery:
    def __init__(self):
        self.ids: list[int] = []
        self.meta: dict[int, dict] = {}
        self.matrix = np.zeros((0, 1), dtype=np.float32)

    def load(self, entries: list[dict]):
        self.ids = [e["staff_id"] for e in entries]
        self.meta = {e["staff_id"]: e for e in entries}
        self.matrix = np.stack([_l2(np.asarray(e["vector"])) for e in entries]) if entries else np.zeros((0, 1), np.float32)

    def match(self, emb: np.ndarray, threshold: float) -> tuple[int | None, float]:
        """Open-set match: returns (None, best) when the best similarity is below threshold."""
        if not self.ids or emb is None or self.matrix.shape[1] != emb.shape[0]:
            return None, 0.0
        sims = self.matrix @ emb
        i = int(np.argmax(sims))
        best = float(sims[i])
        return (self.ids[i], best) if best >= threshold else (None, best)
