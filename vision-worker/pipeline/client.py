import logging
import time

import requests

log = logging.getLogger("worker.client")


class ApiClient:
    def __init__(self, base_url: str, token: str):
        self.base = base_url.rstrip("/") + "/api/v1/internal"
        self.s = requests.Session()
        self.s.headers.update({"X-Internal-Token": token})
        self._last_err = 0.0

    def _call(self, method: str, path: str, **kw):
        kw.setdefault("timeout", 5)
        try:
            r = self.s.request(method, self.base + path, **kw)
            if r.status_code == 401:
                log.error("Backend rejected the internal token. Check INTERNAL_TOKEN in both .env files.")
                return None
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            if time.time() - self._last_err > 10:
                log.warning("Backend unreachable (%s %s): %s", method, path, exc)
                self._last_err = time.time()
            return None

    def config(self):
        return self._call("GET", "/config")

    def heartbeat(self, body: dict):
        return self._call("POST", "/heartbeat", json=body)

    def observations(self, body: dict):
        return self._call("POST", "/observations", json=body)

    def frame(self, code: str, jpeg: bytes):
        return self._call("POST", f"/frames/{code}", data=jpeg, headers={"Content-Type": "image/jpeg"}, timeout=3)

    def pending_enrollment(self, model: str):
        return self._call("GET", "/enrollment/pending", params={"model": model})

    def enrollment_images(self, staff_id: int):
        return self._call("GET", f"/enrollment/{staff_id}/images", timeout=20)

    def save_embedding(self, staff_id: int, body: dict):
        return self._call("POST", f"/enrollment/{staff_id}/embedding", json=body)

    def gallery(self, model: str):
        return self._call("GET", "/gallery", params={"model": model})
