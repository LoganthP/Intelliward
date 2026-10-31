import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.identity_fusion import TrackIdentity  # noqa: E402
from pipeline.role_classifier import classify  # noqa: E402
from pipeline.simulator import Scenario, render  # noqa: E402
from pipeline.tracker import IoUTracker  # noqa: E402


def solid(bgr):
    return np.full((60, 40, 3), bgr, np.uint8)


def test_role_colors():
    assert classify(solid((200, 120, 40)))[0] == "blue"
    assert classify(solid((60, 170, 60)))[0] == "green"
    assert classify(solid((30, 130, 240)))[0] == "orange"
    assert classify(solid((250, 250, 250)))[0] == "white"


def test_role_color_under_warm_cast_with_scene_reference():
    from pipeline.role_classifier import frame_gains
    scene = np.full((200, 200, 3), (180, 180, 180), np.float32)
    scene[60:120, 80:120] = (200, 120, 40)          # blue uniform in a neutral room
    cast = scene * np.array([0.7, 0.95, 1.35])      # strong warm cast (B down, R up)
    cast = np.clip(cast, 0, 255).astype(np.uint8)
    crop = cast[60:120, 80:120]
    assert classify(crop, frame_gains(cast))[0] == "blue"


def test_fusion_requires_consistent_votes_and_open_set():
    t = TrackIdentity()
    t.add_vote(7, 0.6, 2)
    assert t.status == "pending"
    t.add_vote(7, 0.62, 2)
    assert t.status == "verified" and t.staff_id == 7
    u = TrackIdentity()
    for _ in range(3):
        u.add_vote(None, 0.2, 2)
    assert u.status == "unknown" and u.staff_id is None


def test_verified_identity_never_swaps_silently():
    t = TrackIdentity()
    t.add_vote(1, 0.7, 2)
    t.add_vote(1, 0.7, 2)
    t.add_vote(2, 0.7, 2)
    assert t.staff_id == 1
    t.add_vote(2, 0.7, 2)
    t.add_vote(2, 0.7, 2)
    assert t.status == "pending" and t.staff_id is None


def test_iou_tracker_keeps_ids():
    tr = IoUTracker()
    a = tr.update([(10, 10, 50, 100, 0.9)])
    b = tr.update([(12, 11, 52, 101, 0.9)])
    assert a[0][0] == b[0][0]


def test_simulator_renders():
    cam = {"code": "CAM-02", "ward_id": 2, "zones": []}
    staff = [{"id": 1, "staff_code": "NUR-001", "name": "A B", "role": "nurse", "ward_ids": [2]},
             {"id": 3, "staff_code": "OT-001", "name": "C D", "role": "ot_staff", "ward_ids": [3]}]
    sc = Scenario(cam, staff, {"nurse": "blue", "ot_staff": "green"})
    found = any(sc.state(t) for t in range(0, 150, 5))
    assert found
    assert render(cam, sc.state(20)).shape == (540, 960, 3)
