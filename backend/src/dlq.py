"""
BookUdecate V1.0 — Dead Letter Queue (A4)
=======================================
SQLite-backed DLQ for chunks that fail Phase 2 or Phase 4 processing.
Any chunk that exhausts all retries is stored here instead of being
silently discarded or inserted as stub text.

Usage:
    from src.dlq import DLQ
    dlq = DLQ()
    dlq.push(chunk_id="chunk_42", chunk_text="...", error_msg="rate limit")
    failures = dlq.get_all()
    dlq.retry_all(processor_fn)   # re-run all failed chunks
"""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DLQ_PATH = Path("data/output/dlq.db")


class DLQ:
    """Dead Letter Queue backed by SQLite."""

    def __init__(self, db_path: Path = DLQ_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS failed_chunks (
                id          TEXT PRIMARY KEY,
                phase       INTEGER DEFAULT 4,
                chunk_text  TEXT,
                error_msg   TEXT,
                retry_count INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT,
                updated_at  TEXT
            )
        """)
        self.conn.commit()

    def push(self, chunk_id: str, chunk_text: str, error_msg: str, phase: int = 4):
        """Add a failed chunk to the DLQ."""
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT OR REPLACE INTO failed_chunks
            (id, phase, chunk_text, error_msg, retry_count, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0, 'pending', ?, ?)
        """,
            (chunk_id, phase, chunk_text, str(error_msg)[:500], now, now),
        )
        self.conn.commit()
        print(
            f"[DLQ] ⚠️  Chunk {chunk_id} (Phase {phase}) pushed to Dead Letter Queue."
        )

    def get_all(self, status: str = "pending") -> list[dict]:
        """Retrieve all pending failures."""
        rows = self.conn.execute(
            "SELECT id, phase, chunk_text, error_msg, retry_count FROM failed_chunks WHERE status = ?",
            (status,),
        ).fetchall()
        return [
            {"id": r[0], "phase": r[1], "text": r[2], "error": r[3], "retries": r[4]}
            for r in rows
        ]

    def mark_resolved(self, chunk_id: str):
        """Mark a chunk as successfully retried."""
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            "UPDATE failed_chunks SET status='resolved', updated_at=? WHERE id=?",
            (now, chunk_id),
        )
        self.conn.commit()

    def retry_all(self, processor_fn, max_retries: int = 3):
        """
        Re-run all pending failures through a processor function.
        processor_fn(chunk_text: str) -> dict | None
        """
        pending = self.get_all()
        print(f"[DLQ] 🔁 Retrying {len(pending)} failed chunks...")
        recovered = 0
        for item in pending:
            for attempt in range(max_retries):
                try:
                    result = processor_fn(item["text"])
                    if result and "error" not in result:
                        self.mark_resolved(item["id"])
                        recovered += 1
                        break
                except Exception as e:
                    print(
                        f"[DLQ] ⚠️  Retry {attempt+1}/{max_retries} failed for {item['id']}: {e}"
                    )
        print(f"[DLQ] ✅ Recovered {recovered}/{len(pending)} chunks from DLQ.")
        return recovered

    def summary(self) -> dict:
        """Return a count of DLQ items by status."""
        rows = self.conn.execute(
            "SELECT status, COUNT(*) FROM failed_chunks GROUP BY status"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def close(self):
        self.conn.close()
