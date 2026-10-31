"""Threaded frame capture with reconnect. Always keeps only the newest frame (bounded queue of 1)."""
import logging
import threading
import time
from datetime import datetime, timezone

import cv2

log = logging.getLogger("worker.capture")


def open_source(source: str):
    src = source.strip()
    if src.isdigit():
        idx = int(src)
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") and _is_windows() else cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap = cv2.VideoCapture(idx)
        return cap, False
    cap = cv2.VideoCapture(src)
    is_file = not src.lower().startswith(("rtsp://", "http://", "https://"))
    return cap, is_file


def _is_windows():
    import os
    return os.name == "nt"


class FrameSource(threading.Thread):
    def __init__(self, code: str, source: str):
        super().__init__(daemon=True, name=f"capture-{code}")
        self.code = code
        self.source = source
        self._lock = threading.Lock()
        self._frame = None
        self._ts = None
        self._seq = 0
        self.error: str | None = None
        self.stop_event = threading.Event()

    def run(self):
        backoff = 1.0
        while not self.stop_event.is_set():
            cap, is_file = open_source(self.source)
            if not cap.isOpened():
                self.error = f"Cannot open video source '{self.source}'"
                log.warning("[%s] %s, retrying in %.0fs", self.code, self.error, backoff)
                self.stop_event.wait(backoff)
                backoff = min(backoff * 2, 15)
                continue
            self.error = None
            backoff = 1.0
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            delay = 1.0 / fps if is_file and fps > 0 else 0
            log.info("[%s] capturing from %s", self.code, self.source)
            failures = 0
            while not self.stop_event.is_set():
                t0 = time.time()
                ok, frame = cap.read()
                if not ok:
                    if is_file:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop recorded footage
                        failures += 1
                        if failures > 3:
                            break
                        continue
                    failures += 1
                    if failures > 30:
                        self.error = "Video source stopped delivering frames"
                        break
                    time.sleep(0.05)
                    continue
                failures = 0
                with self._lock:
                    self._frame = frame
                    self._ts = datetime.now(timezone.utc)
                    self._seq += 1
                if delay:
                    time.sleep(max(0, delay - (time.time() - t0)))
            cap.release()
        log.info("[%s] capture stopped", self.code)

    def latest(self):
        with self._lock:
            return self._seq, self._frame, self._ts

    def stop(self):
        self.stop_event.set()
