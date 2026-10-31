"""Pure verification logic, usable on database rows or in-memory copies (tamper simulations)."""
import json
from dataclasses import dataclass, field

from .chain import GENESIS_HASH, anchor_hash, chain_hash
from .merkle import merkle_root


@dataclass
class VerifyReport:
    ok: bool = True
    events_checked: int = 0
    batches_checked: int = 0
    anchors_checked: int = 0
    head_hash: str = GENESIS_HASH
    last_anchored_sequence: int = 0
    last_verified_anchored_sequence: int = 0
    unanchored_events: int = 0
    issues: list[dict] = field(default_factory=list)

    def fail(self, code: str, message: str, sequence: int | None = None):
        self.ok = False
        if len(self.issues) < 50:
            self.issues.append({"code": code, "message": message, "sequence": sequence})

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def verify(events: list[dict], batches: list[dict], anchors: list[dict] | None) -> VerifyReport:
    """events: [{sequence, event_id, payload, prev_hash, curr_hash}] in stored order
    batches: [{id, first_sequence, last_sequence, merkle_root, anchor_hash}]
    anchors: external anchor records or None (chain-only verification)."""
    r = VerifyReport()
    prev = GENESIS_HASH
    by_seq: dict[int, dict] = {}
    expected_seq = 1
    for ev in events:
        seq = ev["sequence"]
        r.events_checked += 1
        if seq != expected_seq:
            r.fail("SEQUENCE_GAP", f"Expected sequence {expected_seq} but found {seq}", seq)
            expected_seq = seq
        if ev["prev_hash"] != prev:
            r.fail("BROKEN_LINK", "prev_hash does not match the previous event's hash", seq)
        recomputed = chain_hash(ev["prev_hash"], ev["payload"])
        if recomputed != ev["curr_hash"]:
            r.fail("HASH_MISMATCH", "Event content does not match its stored hash", seq)
        try:
            body = json.loads(ev["payload"])
            if body.get("sequence") != seq or body.get("event_id") != ev["event_id"]:
                r.fail("METADATA_MISMATCH", "Sequence or event id differs from the hashed payload", seq)
        except ValueError:
            r.fail("INVALID_PAYLOAD", "Payload is not valid JSON", seq)
        by_seq[seq] = ev
        prev = ev["curr_hash"]
        expected_seq += 1
    r.head_hash = prev
    max_seq = events[-1]["sequence"] if events else 0

    # Batches stored in the database
    prev_anchor = GENESIS_HASH
    for b in batches:
        r.batches_checked += 1
        leaves = [by_seq[s]["curr_hash"] for s in range(b["first_sequence"], b["last_sequence"] + 1) if s in by_seq]
        if len(leaves) != b["last_sequence"] - b["first_sequence"] + 1:
            r.fail("BATCH_INCOMPLETE", f"Batch {b['id']} references missing events", b["first_sequence"])
        elif merkle_root(leaves) != b["merkle_root"]:
            r.fail("MERKLE_MISMATCH", f"Batch {b['id']} Merkle root does not match its events", b["first_sequence"])
        if anchor_hash(prev_anchor, b["merkle_root"]) != b["anchor_hash"]:
            r.fail("ANCHOR_CHAIN", f"Batch {b['id']} anchor hash is inconsistent", b["first_sequence"])
        prev_anchor = b["anchor_hash"]
        r.last_anchored_sequence = max(r.last_anchored_sequence, b["last_sequence"])

    # Independent anchors (detect full-chain rewrites and truncation)
    if anchors is not None:
        db_batches = {b["id"]: b for b in batches}
        prev_ext = GENESIS_HASH
        verified_upto = 0
        anchor_ok = True
        for a in anchors:
            r.anchors_checked += 1
            if anchor_hash(prev_ext, a["merkle_root"]) != a["anchor_hash"]:
                r.fail("EXTERNAL_ANCHOR_CORRUPT", f"External anchor {a['batch_id']} is internally inconsistent")
                anchor_ok = False
            prev_ext = a["anchor_hash"]
            if a["last_sequence"] > max_seq:
                r.fail("TRUNCATION", f"Anchor {a['batch_id']} covers up to sequence {a['last_sequence']} "
                                     f"but the log ends at {max_seq}", a["last_sequence"])
                anchor_ok = False
                continue
            leaves = [by_seq[s]["curr_hash"] for s in range(a["first_sequence"], a["last_sequence"] + 1) if s in by_seq]
            if len(leaves) != a["last_sequence"] - a["first_sequence"] + 1 or merkle_root(leaves) != a["merkle_root"]:
                r.fail("ANCHOR_MISMATCH", f"Events {a['first_sequence']}-{a['last_sequence']} differ from the "
                                          f"independently anchored Merkle root", a["first_sequence"])
                anchor_ok = False
            b = db_batches.get(a["batch_id"])
            if b is None or b["merkle_root"] != a["merkle_root"]:
                r.fail("BATCH_ANCHOR_DIVERGENCE", f"Database batch {a['batch_id']} differs from external anchor")
                anchor_ok = False
            if anchor_ok:
                verified_upto = a["last_sequence"]
        if len(batches) > len(anchors):
            r.fail("UNANCHORED_BATCH", "Database contains batches that were never anchored externally")
        r.last_verified_anchored_sequence = verified_upto
        r.unanchored_events = max(0, max_seq - (anchors[-1]["last_sequence"] if anchors else 0))
    else:
        r.unanchored_events = max(0, max_seq - r.last_anchored_sequence)
    return r
