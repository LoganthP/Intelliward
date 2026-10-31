"""Independent anchor store.

Anchors are appended to a JSONL file that lives OUTSIDE the main database
(ANCHOR_DIR). The store exposes append and read operations only; there is no
update or delete. For a stronger deployment, place ANCHOR_DIR on storage the
database administrator cannot write (separate machine, WORM bucket, etc.).
"""
import json
import os
import threading
from pathlib import Path

from .chain import GENESIS_HASH


class AnchorStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.file = self.directory / "anchors.jsonl"
        self._lock = threading.Lock()

    def read_all(self) -> list[dict]:
        if not self.file.exists():
            return []
        out = []
        with self.file.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def last_anchor_hash(self) -> str:
        items = self.read_all()
        return items[-1]["anchor_hash"] if items else GENESIS_HASH

    def append(self, record: dict) -> str:
        with self._lock:
            with self.file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        return f"{self.file.name}#batch-{record['batch_id']}"
