"""Controlled tamper simulations on in-memory copies (never on the real log)."""
import copy
import json

from .chain import GENESIS_HASH, anchor_hash, chain_hash
from .merkle import merkle_root
from .verifier import verify

ATTACKS = {
    "modification": "Change one event's content without updating hashes",
    "deletion": "Remove one event from the middle of the log",
    "insertion": "Insert a forged event with a self-consistent hash",
    "reordering": "Swap two adjacent events",
    "truncation": "Drop the most recent events, including anchored ones",
    "full_rewrite": "Modify an event and recompute every hash and Merkle root in the database",
}


def _rechain(events: list[dict]) -> list[dict]:
    prev = GENESIS_HASH
    for i, ev in enumerate(events, start=1):
        body = json.loads(ev["payload"])
        body["sequence"] = i
        ev["sequence"] = i
        ev["payload"] = json.dumps(body, sort_keys=True, separators=(",", ":"))
        ev["prev_hash"] = prev
        ev["curr_hash"] = chain_hash(prev, ev["payload"])
        prev = ev["curr_hash"]
    return events


def _rebatch(events: list[dict], batches: list[dict]) -> list[dict]:
    by_seq = {e["sequence"]: e for e in events}
    prev = GENESIS_HASH
    for b in batches:
        leaves = [by_seq[s]["curr_hash"] for s in range(b["first_sequence"], b["last_sequence"] + 1) if s in by_seq]
        b["merkle_root"] = merkle_root(leaves)
        b["anchor_hash"] = anchor_hash(prev, b["merkle_root"])
        prev = b["anchor_hash"]
    return batches


def apply_attack(name: str, events: list[dict], batches: list[dict]):
    ev = copy.deepcopy(events)
    bt = copy.deepcopy(batches)
    mid = max(0, len(ev) // 2 - 1)
    if name == "modification":
        body = json.loads(ev[mid]["payload"])
        body.setdefault("data", {})["tampered"] = True
        ev[mid]["payload"] = json.dumps(body, sort_keys=True, separators=(",", ":"))
    elif name == "deletion":
        del ev[mid]
    elif name == "insertion":
        forged = copy.deepcopy(ev[mid])
        body = json.loads(forged["payload"])
        body["event_id"] = forged["event_id"] = "forged-event"
        body["data"] = {"forged": True}
        forged["payload"] = json.dumps(body, sort_keys=True, separators=(",", ":"))
        forged["prev_hash"] = ev[mid]["curr_hash"]
        forged["curr_hash"] = chain_hash(forged["prev_hash"], forged["payload"])
        ev.insert(mid + 1, forged)
    elif name == "reordering":
        ev[mid], ev[mid + 1] = ev[mid + 1], ev[mid]
    elif name == "truncation":
        cut = max(1, min(len(ev) - 1, (bt[-1]["last_sequence"] if bt else len(ev)) - 2))
        ev = ev[:cut]
        bt = [b for b in bt if b["last_sequence"] <= cut]
        # attacker also rewrites the head so the remaining chain is internally consistent
    elif name == "full_rewrite":
        body = json.loads(ev[mid]["payload"])
        body.setdefault("data", {})["tampered"] = True
        ev[mid]["payload"] = json.dumps(body, sort_keys=True, separators=(",", ":"))
        ev = _rechain(ev)
        bt = _rebatch(ev, bt)
    return ev, bt


def run_simulations(events: list[dict], batches: list[dict], anchors: list[dict]) -> list[dict]:
    results = []
    for name, description in ATTACKS.items():
        ev, bt = apply_attack(name, events, batches)
        with_anchor = verify(ev, bt, anchors)
        chain_only = verify(ev, bt, None)
        results.append({
            "attack": name,
            "description": description,
            "detected_with_anchors": not with_anchor.ok,
            "detected_chain_only": not chain_only.ok,
            "first_issue": with_anchor.issues[0] if with_anchor.issues else None,
        })
    return results
