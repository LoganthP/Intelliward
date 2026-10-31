"""Minimal IoU tracker used only when Ultralytics/ByteTrack is not installed."""
import numpy as np


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


class IoUTracker:
    def __init__(self, iou_threshold=0.3, max_missed=15):
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.tracks: dict[int, dict] = {}
        self.next_id = 1

    def update(self, boxes: list[tuple]) -> list[tuple]:
        """boxes: [(x1,y1,x2,y2,conf)] -> [(track_id,x1,y1,x2,y2,conf)]"""
        assigned, out = set(), []
        for tid, t in sorted(self.tracks.items(), key=lambda kv: kv[1]["missed"]):
            best, best_iou = None, self.iou_threshold
            for i, b in enumerate(boxes):
                if i in assigned:
                    continue
                v = iou(t["box"], b)
                if v > best_iou:
                    best, best_iou = i, v
            if best is not None:
                assigned.add(best)
                t["box"], t["missed"] = boxes[best][:4], 0
                out.append((tid, *boxes[best]))
            else:
                t["missed"] += 1
        for i, b in enumerate(boxes):
            if i not in assigned:
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = {"box": b[:4], "missed": 0}
                out.append((tid, *b))
        self.tracks = {k: v for k, v in self.tracks.items() if v["missed"] <= self.max_missed}
        return out

    def active_ids(self):
        return set(self.tracks)
