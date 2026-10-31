"""Per-track identity state: open-set votes, verification, unknown state, short occlusion continuity."""
from collections import deque
from dataclasses import dataclass, field


@dataclass
class TrackIdentity:
    status: str = "pending"            # pending | verified | unknown
    staff_id: int | None = None
    similarity: float = 0.0
    votes: deque = field(default_factory=lambda: deque(maxlen=6))
    contradictions: int = 0
    role_color: str = "unknown"
    role_conf: float = 0.0
    last_face_frame: int = -1000

    def add_vote(self, staff_id: int | None, sim: float, required: int):
        self.votes.append((staff_id, sim))
        if self.status == "verified":
            if staff_id is not None and staff_id != self.staff_id:
                self.contradictions += 1
                if self.contradictions >= 3:  # repeated confident disagreement: drop to pending, never auto-swap
                    self.status, self.staff_id, self.contradictions = "pending", None, 0
                    self.votes.clear()
            elif staff_id == self.staff_id:
                self.contradictions = 0
                self.similarity = max(self.similarity * 0.8, sim)
            return
        recent = list(self.votes)[-required:]
        if len(recent) >= required and all(v[0] is not None and v[0] == recent[0][0] for v in recent):
            self.status, self.staff_id = "verified", recent[0][0]
            self.similarity = sum(v[1] for v in recent) / len(recent)
            return
        misses = [v for v in self.votes if v[0] is None]
        if len(self.votes) >= 3 and len(misses) >= len(self.votes) - 1:
            self.status = "unknown"
            self.similarity = max(v[1] for v in self.votes)


class IdentityFusion:
    def __init__(self):
        self.tracks: dict[str, TrackIdentity] = {}

    def get(self, key: str) -> TrackIdentity:
        if key not in self.tracks:
            self.tracks[key] = TrackIdentity()
        return self.tracks[key]

    def prune(self, alive: set[str]) -> list[str]:
        lost = [k for k in self.tracks if k not in alive]
        for k in lost:
            del self.tracks[k]
        return lost
