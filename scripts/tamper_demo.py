"""Live tamper demonstration on the REAL audit log (for the faculty demo).

    python scripts/tamper_demo.py modify      change one anchored event directly in the database
    python scripts/tamper_demo.py rewrite     modify an event AND recompute every hash and DB Merkle root
    python scripts/tamper_demo.py restore     put the original rows back

Then press "Verify integrity" in the dashboard. A backup of the touched rows is kept in data/tamper_backup.json.
Run with the project virtual environment:  .venv\\Scripts\\python scripts\\tamper_demo.py modify  (Windows)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.models import AuditBatch, AuditEvent  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.integrity.chain import GENESIS_HASH, anchor_hash, chain_hash  # noqa: E402
from app.integrity.merkle import merkle_root  # noqa: E402
from app.core.config import settings  # noqa: E402

BACKUP = settings.data_path / "tamper_backup.json"


def backup(db):
    if BACKUP.exists():
        sys.exit("A backup already exists. Run `restore` first.")
    rows = {"events": [{"sequence": e.sequence, "payload": e.payload, "prev_hash": e.prev_hash, "curr_hash": e.curr_hash}
                       for e in db.query(AuditEvent).all()],
            "batches": [{"id": b.id, "merkle_root": b.merkle_root, "anchor_hash": b.anchor_hash} for b in db.query(AuditBatch).all()]}
    BACKUP.write_text(json.dumps(rows))


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    with SessionLocal() as db:
        if action in ("modify", "rewrite"):
            target = db.query(AuditBatch).order_by(AuditBatch.id.asc()).first()
            if target is None:
                sys.exit("No anchored batch yet. Click 'Anchor now' in the dashboard first.")
            backup(db)
            seq = (target.first_sequence + target.last_sequence) // 2
            ev = db.get(AuditEvent, seq)
            body = json.loads(ev.payload)
            body["data"]["tampered_by_demo"] = True
            ev.payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
            if action == "rewrite":
                prev = GENESIS_HASH
                events = db.query(AuditEvent).order_by(AuditEvent.sequence).all()
                for e in events:
                    e.prev_hash = prev
                    e.curr_hash = chain_hash(prev, e.payload)
                    prev = e.curr_hash
                by = {e.sequence: e.curr_hash for e in events}
                a = GENESIS_HASH
                for b in db.query(AuditBatch).order_by(AuditBatch.id).all():
                    b.merkle_root = merkle_root([by[s] for s in range(b.first_sequence, b.last_sequence + 1)])
                    b.anchor_hash = a = anchor_hash(a, b.merkle_root)
            db.commit()
            print(f"Tampered with event #{seq} ({action}). Now click 'Verify integrity' in the dashboard.")
        elif action == "restore":
            if not BACKUP.exists():
                sys.exit("Nothing to restore.")
            data = json.loads(BACKUP.read_text())
            for r in data["events"]:
                e = db.get(AuditEvent, r["sequence"])
                if e:
                    e.payload, e.prev_hash, e.curr_hash = r["payload"], r["prev_hash"], r["curr_hash"]
            for r in data["batches"]:
                b = db.get(AuditBatch, r["id"])
                if b:
                    b.merkle_root, b.anchor_hash = r["merkle_root"], r["anchor_hash"]
            db.commit()
            BACKUP.unlink()
            print("Original audit rows restored.")
        else:
            print(__doc__)


if __name__ == "__main__":
    main()
