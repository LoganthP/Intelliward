"""Audit writer: a single serialized append path for the hash chain plus Merkle batching and anchoring."""
import threading
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutil import iso, utcnow
from app.db.models import AuditBatch, AuditEvent
from app.integrity.anchor import AnchorStore
from app.integrity.canonical import SCHEMA_VERSION, canonical_json
from app.integrity.chain import GENESIS_HASH, anchor_hash, chain_hash
from app.integrity.merkle import merkle_root
from app.integrity.verifier import verify

write_lock = threading.RLock()
anchor_store = AnchorStore(settings.anchor_path)


def append(db: Session, event_type: str, data: dict, event_id: str | None = None) -> AuditEvent:
    """Append inside the caller's transaction. The lock serializes chain-head computation; the caller commits.
    Duplicate event_ids are idempotent (returns the existing record)."""
    with write_lock:
        db.flush()
        if event_id:
            existing = db.query(AuditEvent).filter(AuditEvent.event_id == event_id).first()
            if existing:
                return existing
        head = db.query(AuditEvent).order_by(AuditEvent.sequence.desc()).first()
        seq = (head.sequence + 1) if head else 1
        prev = head.curr_hash if head else GENESIS_HASH
        now = utcnow()
        eid = event_id or uuid.uuid4().hex
        body = {
            "schema_version": SCHEMA_VERSION,
            "sequence": seq,
            "event_id": eid,
            "event_type": event_type,
            "occurred_at": iso(now),
            "data": data,
        }
        payload = canonical_json(body)
        ev = AuditEvent(sequence=seq, event_id=eid, event_type=event_type, occurred_at=now,
                        payload=payload, prev_hash=prev, curr_hash=chain_hash(prev, payload))
        db.add(ev)
        db.flush()
        return ev


def committed_append(db: Session, event_type: str, data: dict, event_id: str | None = None):
    with write_lock:
        ev = append(db, event_type, data, event_id)
        db.commit()
        return ev


def _rows(db: Session):
    events = [{"sequence": e.sequence, "event_id": e.event_id, "payload": e.payload,
               "prev_hash": e.prev_hash, "curr_hash": e.curr_hash}
              for e in db.query(AuditEvent).order_by(AuditEvent.sequence.asc()).all()]
    batches = [{"id": b.id, "first_sequence": b.first_sequence, "last_sequence": b.last_sequence,
                "merkle_root": b.merkle_root, "anchor_hash": b.anchor_hash}
               for b in db.query(AuditBatch).order_by(AuditBatch.id.asc()).all()]
    return events, batches


def anchor_pending(db: Session, force: bool = False) -> AuditBatch | None:
    """Group unanchored events into a Merkle batch and publish an independent anchor."""
    with write_lock:
        last = db.query(AuditBatch).order_by(AuditBatch.id.desc()).first()
        first_seq = (last.last_sequence + 1) if last else 1
        max_seq = db.query(func.max(AuditEvent.sequence)).scalar() or 0
        pending = max_seq - first_seq + 1
        if pending <= 0:
            return None
        if not force and pending < settings.audit_batch_size:
            oldest = db.query(AuditEvent).filter(AuditEvent.sequence == first_seq).first()
            if oldest is None or (utcnow() - oldest.occurred_at).total_seconds() < settings.audit_batch_max_age_seconds:
                return None
        last_seq = min(max_seq, first_seq + max(settings.audit_batch_size, 1) * 4 - 1)
        leaves = [h for (h,) in db.query(AuditEvent.curr_hash)
                  .filter(AuditEvent.sequence >= first_seq, AuditEvent.sequence <= last_seq)
                  .order_by(AuditEvent.sequence.asc()).all()]
        root = merkle_root(leaves)
        prev_anchor = anchor_store.last_anchor_hash()
        db_prev = last.anchor_hash if last else GENESIS_HASH
        if prev_anchor != db_prev:
            # The independent store and the database disagree; do not paper over it.
            raise RuntimeError("Anchor store head differs from database batches; run audit verification")
        a_hash = anchor_hash(prev_anchor, root)
        batch_id = (last.id + 1) if last else 1
        record = {"batch_id": batch_id, "first_sequence": first_seq, "last_sequence": last_seq,
                  "merkle_root": root, "prev_anchor": prev_anchor, "anchor_hash": a_hash,
                  "anchored_at": iso(utcnow())}
        ref = anchor_store.append(record)
        batch = AuditBatch(id=batch_id, first_sequence=first_seq, last_sequence=last_seq,
                           merkle_root=root, anchor_hash=a_hash, external_reference=ref)
        db.add(batch)
        db.commit()
        return batch


def verify_db(db: Session) -> dict:
    events, batches = _rows(db)
    return verify(events, batches, anchor_store.read_all()).as_dict()


def snapshot(db: Session):
    events, batches = _rows(db)
    return events, batches, anchor_store.read_all()
