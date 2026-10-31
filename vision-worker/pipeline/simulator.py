"""Synthetic ward scenario for cameras whose source is 'sim'.

It renders a simple mock ward and emits observations exactly like the real pipeline, so the backend,
dashboard, task engine, alerts and audit chain can be demonstrated without a webcam or AI models.
Identities here are SIMULATED (model_version "simulator") and must never be reported as recognition accuracy.
"""
import math
import os
import random

import cv2
import numpy as np

UNIFORM_BGR = {"blue": (214, 140, 60), "white": (245, 245, 245), "green": (110, 170, 60),
               "orange": (40, 140, 245), "gray": (150, 150, 150)}
PERIOD = 150.0
SPEED = max(0.1, float(os.getenv("SIM_SPEED", "1")))  # >1 plays the scenario faster (quick demos)


def _lerp_path(points, t):
    """points: [(time, x, y)], returns (x, y) or None if outside the path's time span."""
    if t < points[0][0] or t > points[-1][0]:
        return None
    for (t0, x0, y0), (t1, x1, y1) in zip(points, points[1:]):
        if t0 <= t <= t1:
            a = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            return x0 + (x1 - x0) * a, y0 + (y1 - y0) * a
    return points[-1][1], points[-1][2]


class Scenario:
    def __init__(self, camera: dict, staff: list[dict], color_map: dict):
        self.camera = camera
        ward = camera["ward_id"]
        allowed = [s for s in staff if ward in s.get("ward_ids", [])]
        others = [s for s in staff if ward not in s.get("ward_ids", [])]
        self.actors = []
        if allowed:
            a = allowed[0]
            self.actors.append({"key": "A", "staff": a, "color": color_map.get(a["role"], "gray"),
                                "path": [(5, -0.1, 0.92), (12, 0.22, 0.9), (55, 0.24, 0.88),
                                         (62, 0.8, 0.9), (95, 0.82, 0.88), (102, 1.1, 0.9)],
                                "gaps": [(40, 44)]})
        self.actors.append({"key": "U", "staff": None, "color": "gray",
                            "path": [(28, 1.1, 0.95), (36, 0.55, 0.93), (52, 0.5, 0.95), (58, 1.1, 0.95)],
                            "gaps": []})
        if len(allowed) > 1:
            b = allowed[1]
            wrong = next((c for c in ("green", "orange", "blue", "white") if c != color_map.get(b["role"])), "gray")
            self.actors.append({"key": "B", "staff": b, "color": wrong,
                                "path": [(65, -0.1, 0.94), (72, 0.4, 0.92), (92, 0.45, 0.93), (98, -0.1, 0.94)],
                                "gaps": []})
        if others:
            c = others[0]
            self.actors.append({"key": "X", "staff": c, "color": color_map.get(c["role"], "gray"),
                                "path": [(110, 1.1, 0.9), (118, 0.6, 0.88), (132, 0.62, 0.9), (138, 1.1, 0.9)],
                                "gaps": []})
        random.seed(hash(camera["code"]) & 0xFFFF)
        self.offset = random.uniform(0, 40)

    def state(self, now: float):
        now = now * SPEED
        cycle = int((now + self.offset) // PERIOD)
        t = (now + self.offset) % PERIOD
        people = []
        for a in self.actors:
            pos = _lerp_path(a["path"], t)
            if pos is None or any(g0 <= t <= g1 for g0, g1 in a["gaps"]):
                continue
            appeared = t - a["path"][0][0]
            if a["staff"] is not None:
                status = "verified" if appeared > 2.0 else "pending"
            else:
                status = "unknown" if appeared > 3.0 else "pending"
            x, y = pos
            sway = 0.006 * math.sin(now * 3 + hash(a["key"]) % 7)
            cx = x + sway
            w, h = 0.11, 0.46
            people.append({"track_id": f"SIM{self.camera['code'][-2:]}-{cycle}{a['key']}",
                           "box": (cx - w / 2, y - h, cx + w / 2, y), "status": status, "actor": a})
        return people


def render(camera: dict, people: list[dict], width=960, height=540) -> np.ndarray:
    img = np.full((height, width, 3), (246, 241, 236), np.uint8)
    cv2.rectangle(img, (0, int(height * 0.42)), (width, height), (226, 230, 232), -1)
    for i in range(0, width, 48):
        cv2.line(img, (i, int(height * 0.42)), (i - 80, height), (214, 219, 222), 1)
    cv2.rectangle(img, (int(width * 0.04), int(height * 0.55)), (int(width * 0.36), int(height * 0.78)),
                  (250, 250, 250), -1)
    cv2.rectangle(img, (int(width * 0.04), int(height * 0.55)), (int(width * 0.36), int(height * 0.78)),
                  (190, 195, 200), 2)
    cv2.rectangle(img, (int(width * 0.05), int(height * 0.52)), (int(width * 0.12), int(height * 0.6)),
                  (235, 226, 214), -1)
    cv2.rectangle(img, (int(width * 0.7), int(height * 0.55)), (int(width * 0.92), int(height * 0.8)),
                  (200, 210, 214), -1)
    cv2.circle(img, (int(width * 0.81), int(height * 0.5)), int(height * 0.06), (90, 160, 110), -1)
    cv2.rectangle(img, (int(width * 0.42), int(height * 0.08)), (int(width * 0.58), int(height * 0.34)),
                  (230, 236, 240), -1)
    for p in people:
        x1, y1, x2, y2 = p["box"]
        X1, Y1, X2, Y2 = int(x1 * width), int(y1 * height), int(x2 * width), int(y2 * height)
        col = UNIFORM_BGR.get(p["actor"]["color"], UNIFORM_BGR["gray"])
        bw = X2 - X1
        head_r = int(bw * 0.28)
        cv2.circle(img, ((X1 + X2) // 2, Y1 + head_r + 2), head_r, (150, 180, 215), -1)
        cv2.rectangle(img, (X1 + int(bw * 0.08), Y1 + 2 * head_r + 4), (X2 - int(bw * 0.08), Y2 - int((Y2 - Y1) * 0.3)),
                      col, -1)
        cv2.rectangle(img, (X1 + int(bw * 0.2), Y2 - int((Y2 - Y1) * 0.3)), (X2 - int(bw * 0.2), Y2), (90, 90, 100), -1)
    return img
