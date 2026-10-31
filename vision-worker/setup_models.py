"""Download the OpenCV face models (YuNet detector, SFace recognizer) and verify their SHA-256."""
import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS = Path(__file__).resolve().parent / "models"
FILES = {
    "face_detection_yunet_2023mar.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    "face_recognition_sface_2021dec.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    MODELS.mkdir(exist_ok=True)
    ok = True
    for name, (url, digest) in FILES.items():
        path = MODELS / name
        if path.exists() and sha256(path) == digest:
            print(f"[ok] {name}")
            continue
        print(f"[download] {name}")
        try:
            urllib.request.urlretrieve(url, path)
        except Exception as exc:
            print(f"[error] {name}: {exc}\n        Download it manually from {url} into {MODELS}")
            ok = False
            continue
        if sha256(path) != digest:
            print(f"[error] {name}: checksum mismatch, deleting the file")
            path.unlink(missing_ok=True)
            ok = False
        else:
            print(f"[ok] {name} verified")
    print("YOLOv8 weights (yolov8n.pt) download automatically on first use when ultralytics is installed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
