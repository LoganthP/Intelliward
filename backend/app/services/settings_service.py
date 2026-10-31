from sqlalchemy.orm import Session

from app.db.models import Setting

DEFAULTS: dict = {
    "face_match_threshold": 0.42,         # cosine similarity, InsightFace ArcFace
    "face_match_threshold_sface": 0.40,   # cosine similarity, OpenCV SFace (OpenCV suggests >= 0.363)
    "face_min_size": 48,                  # px, smaller faces are skipped (quality gate)
    "identity_votes_required": 2,         # consistent matches before a track becomes verified
    "visit_confirm_seconds": 3,           # provisional -> active
    "visit_exit_timeout_seconds": 15,     # unseen this long -> exit
    "visit_merge_window_seconds": 30,     # re-entry within this window extends the same visit
    "unknown_alert_seconds": 6,
    "role_mismatch_observations": 5,
    "role_color_map": {"nurse": "blue", "doctor": "white", "ot_staff": "green", "cleaner": "orange"},
    "frame_stride": 2,                    # process every Nth frame
    "detector_confidence": 0.45,
    "retention_days": 30,
}


def get_all(db: Session) -> dict:
    values = dict(DEFAULTS)
    for row in db.query(Setting).all():
        values[row.key] = row.value
    return values


def get(db: Session, key: str):
    row = db.get(Setting, key)
    return row.value if row is not None else DEFAULTS.get(key)


def update(db: Session, changes: dict) -> dict:
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise KeyError(key)
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    db.flush()
    return get_all(db)
