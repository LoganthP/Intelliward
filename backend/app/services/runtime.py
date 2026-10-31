"""In-memory runtime state: latest annotated frames per camera and worker heartbeat."""
import threading
import time


class FrameStore:
    def __init__(self):
        self._frames: dict[str, tuple[bytes, float]] = {}
        self._lock = threading.Lock()

    def put(self, camera_code: str, jpeg: bytes):
        with self._lock:
            self._frames[camera_code] = (jpeg, time.time())

    def get(self, camera_code: str) -> tuple[bytes, float] | None:
        with self._lock:
            return self._frames.get(camera_code)

    def drop(self, camera_code: str):
        with self._lock:
            self._frames.pop(camera_code, None)


frames = FrameStore()

worker_state: dict = {"last_heartbeat": 0.0, "info": {}}


def worker_online(max_age: float = 15.0) -> bool:
    return time.time() - worker_state["last_heartbeat"] < max_age
