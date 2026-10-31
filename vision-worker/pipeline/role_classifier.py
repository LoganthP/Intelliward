"""Secondary uniform-colour cue from the torso region (HSV). Never used to decide identity."""
import cv2
import numpy as np

COLOR_RANGES = {  # OpenCV hue is 0-179
    "orange": (8, 22),
    "green": (40, 85),
    "blue": (95, 130),
}


def frame_gains(frame: np.ndarray) -> np.ndarray:
    """Gray-world gains estimated on the WHOLE frame (scene reference), not on the uniform itself."""
    means = frame.reshape(-1, 3).astype(np.float32).mean(axis=0) + 1e-6
    gains = means.mean() / means
    return np.clip(gains, 0.6, 1.6)


def apply_gains(img: np.ndarray, gains: np.ndarray | None) -> np.ndarray:
    if gains is None:
        return img
    return np.clip(img.astype(np.float32) * gains, 0, 255).astype(np.uint8)


def torso_crop(frame: np.ndarray, box) -> np.ndarray | None:
    x1, y1, x2, y2 = [int(v) for v in box[:4]]
    w, h = x2 - x1, y2 - y1
    if w < 12 or h < 24:
        return None
    tx1, tx2 = x1 + int(0.25 * w), x2 - int(0.25 * w)
    ty1, ty2 = y1 + int(0.28 * h), y1 + int(0.60 * h)
    H, W = frame.shape[:2]
    crop = frame[max(0, ty1):min(H, ty2), max(0, tx1):min(W, tx2)]
    return crop if crop.size else None


def classify(crop: np.ndarray | None, gains: np.ndarray | None = None) -> tuple[str, float]:
    """Returns (colour label, confidence in [0,1]). 'unknown' when the region is ambiguous.
    gains: optional reference correction from frame_gains()."""
    if crop is None or crop.size == 0:
        return "unknown", 0.0
    hsv = cv2.cvtColor(apply_gains(crop, gains), cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    total = h.size
    counts = {"white": int(np.count_nonzero((s < 45) & (v > 165)))}
    chroma = (s >= 70) & (v >= 50)
    for name, (lo, hi) in COLOR_RANGES.items():
        counts[name] = int(np.count_nonzero(chroma & (h >= lo) & (h <= hi)))
    label = max(counts, key=counts.get)
    labelled = sum(counts.values())
    coverage = counts[label] / total
    if coverage < 0.25 or labelled == 0:
        return "unknown", round(coverage, 3)
    purity = counts[label] / labelled
    return label, round(min(1.0, purity * min(1.0, coverage / 0.5)), 3)
