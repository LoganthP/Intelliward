import json

from app.integrity.anchor import AnchorStore
from app.integrity.canonical import canonical_json
from app.integrity.chain import GENESIS_HASH, anchor_hash, chain_hash
from app.integrity.merkle import merkle_root
from app.integrity.tamper import run_simulations
from app.integrity.verifier import verify


def build_log(n=20, batch=5):
    events, prev = [], GENESIS_HASH
    for i in range(1, n + 1):
        payload = canonical_json({"sequence": i, "event_id": f"e{i}", "event_type": "t", "data": {"i": i}})
        h = chain_hash(prev, payload)
        events.append({"sequence": i, "event_id": f"e{i}", "payload": payload, "prev_hash": prev, "curr_hash": h})
        prev = h
    batches, anchors, a_prev = [], [], GENESIS_HASH
    for bid, start in enumerate(range(1, n + 1, batch), start=1):
        end = min(n, start + batch - 1)
        root = merkle_root([e["curr_hash"] for e in events[start - 1:end]])
        a = anchor_hash(a_prev, root)
        batches.append({"id": bid, "first_sequence": start, "last_sequence": end, "merkle_root": root, "anchor_hash": a})
        anchors.append({"batch_id": bid, "first_sequence": start, "last_sequence": end, "merkle_root": root,
                        "anchor_hash": a})
        a_prev = a
    return events, batches, anchors


def test_clean_log_verifies():
    ev, bt, an = build_log()
    assert verify(ev, bt, an).ok


def test_canonical_is_deterministic():
    assert canonical_json({"b": 1, "a": [2, {"d": 1, "c": 2}]}) == canonical_json({"a": [2, {"c": 2, "d": 1}], "b": 1})


def test_all_six_attacks_detected_with_anchors():
    ev, bt, an = build_log()
    results = run_simulations(ev, bt, an)
    assert len(results) == 6
    assert all(r["detected_with_anchors"] for r in results), results
    rewrite = next(r for r in results if r["attack"] == "full_rewrite")
    assert rewrite["detected_chain_only"] is False  # why external anchors matter


def test_anchor_store_append_only(tmp_path):
    s = AnchorStore(tmp_path)
    assert s.last_anchor_hash() == GENESIS_HASH
    s.append({"batch_id": 1, "anchor_hash": "ab" * 32})
    assert s.read_all()[0]["batch_id"] == 1
    assert json.loads((tmp_path / "anchors.jsonl").read_text().strip())["batch_id"] == 1
