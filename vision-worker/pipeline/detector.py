"""Person detection + tracking. Primary: Ultralytics YOLOv8 with ByteTrack. Fallback: face-anchored or HOG + IoU."""
import logging

import cv2
import numpy as np

from .tracker import IoUTracker

log = logging.getLogger("worker.detector")


def yolo_available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except Exception:
        return False


class YoloByteTrack:
    name = "yolov8+bytetrack"

    def __init__(self, weights: str, device: str, conf: float):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.device = device
        self.conf = conf
        self._ids: set[int] = set()

    def update(self, frame: np.ndarray, faces=None):
        res = self.model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[0], conf=self.conf,
                               device=self.device, verbose=False)[0]
        out = []
        if res.boxes is not None and res.boxes.id is not None:
            xyxy = res.boxes.xyxy.cpu().numpy()
            ids = res.boxes.id.cpu().numpy().astype(int)
            confs = res.boxes.conf.cpu().numpy()
            for b, i, c in zip(xyxy, ids, confs):
                out.append((int(i), float(b[0]), float(b[1]), float(b[2]), float(b[3]), float(c)))
        self._ids = {t[0] for t in out}
        return out


class FallbackDetector:
    """Without YOLO: derive person boxes from detected faces (good for webcam demos), else HOG pedestrians."""
    name = "fallback(face-anchored/hog)+iou"

    def __init__(self, conf: float):
        self.tracker = IoUTracker()
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self.conf = conf

    def update(self, frame: np.ndarray, faces=None):
        h, w = frame.shape[:2]
        boxes = []
        if faces:
            for f in faces:
                x1, y1, x2, y2 = f.box
                fw, fh = x2 - x1, y2 - y1
                boxes.append((max(0, x1 - 1.1 * fw), max(0, y1 - 0.5 * fh), min(w, x2 + 1.1 * fw),
                              min(h, y2 + 5.5 * fh), float(f.score)))
        else:
            scale = 640 / max(w, 1) if w > 640 else 1.0
            small = cv2.resize(frame, None, fx=scale, fy=scale) if scale != 1.0 else frame
            rects, weights = self.hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
            for (x, y, rw, rh), wt in zip(rects, np.ravel(weights) if len(rects) else []):
                if wt >= 0.5:
                    boxes.append((x / scale, y / scale, (x + rw) / scale, (y + rh) / scale, float(min(1.0, wt))))
        return self.tracker.update(boxes)
