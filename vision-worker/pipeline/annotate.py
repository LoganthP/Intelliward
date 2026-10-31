import cv2

COLORS = {"verified": (120, 190, 30), "unknown": (70, 70, 230), "pending": (40, 170, 240)}


def draw(frame, tracks: list[dict], zones: list[dict], label: str):
    h, w = frame.shape[:2]
    for z in zones or []:
        p1 = (int(z["x1"] * w), int(z["y1"] * h))
        p2 = (int(z["x2"] * w), int(z["y2"] * h))
        overlay = frame.copy()
        cv2.rectangle(overlay, p1, p2, (230, 200, 120), -1)
        cv2.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)
        cv2.rectangle(frame, p1, p2, (210, 170, 80), 1)
        cv2.putText(frame, z["name"], (p1[0] + 6, p1[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 110, 30), 1,
                    cv2.LINE_AA)
    for t in tracks:
        x1, y1, x2, y2 = [int(v) for v in t["px"]]
        color = COLORS.get(t["identity_status"], (200, 200, 200))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        text = t.get("label") or t["identity_status"]
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, y1), color, -1)
        cv2.putText(frame, text, (x1 + 4, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, label, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, label, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 60), 1, cv2.LINE_AA)
    return frame
