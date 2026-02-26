"""
BookUdecate V1.0 — Job State Store
================================
In-memory store for all active and recent pipeline jobs.
Backed by a JSON file for persistence across server restarts.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
import threading
from pathlib import Path
from typing import Optional

JOBS_FILE = Path("data/output/jobs.json")


@dataclass
class Job:
    job_id: str
    status: str = "pending"  # pending | processing | completed | failed
    current_phase: int = 0  # 1-4
    progress_percentage: float = 0.0  # 0-100
    message: str = ""
    is_recoverable: bool = False  # True if resume is possible
    resume_phase: Optional[int] = None  # Last completed phase
    eta_phase_seconds: Optional[int] = None
    eta_total_seconds: Optional[int] = None
    pdf_path: Optional[str] = None
    log_lines: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    config: dict = field(default_factory=dict)  # max_new_diagrams, etc.

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        return cls(**d)


class JobStore:
    """Thread-safe in-memory job store with JSON persistence."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._load()

    def create(self, config: dict | None = None) -> Job:
        job_id = str(uuid.uuid4())[:8]
        job = Job(job_id=job_id, config=config or {})
        self._jobs[job_id] = job
        self._save()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        for k, v in kwargs.items():
            if hasattr(job, k):
                setattr(job, k, v)
        job.updated_at = time.time()
        # Removed auto-save to disk for performance
        return job

    def append_log(
        self, job_id: str, message: str, level: str = "INFO", source: str = "Engine"
    ):
        job = self._jobs.get(job_id)
        if job:
            entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "level": level,
                "source": source,
                "message": message,
            }
            job.log_lines.append(entry)
            # Keep last 500 lines only
            if len(job.log_lines) > 500:
                job.log_lines = job.log_lines[-500:]

    def all_jobs(self) -> list[dict]:
        return [j.to_dict() for j in self._jobs.values()]

    def _save(self):
        with self._lock:
            # Simple, stable write instead of fragile atomic swap on Windows
            JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
            serializable = {jid: j.to_dict() for jid, j in self._jobs.items()}
            JOBS_FILE.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    def _load(self):
        if JOBS_FILE.exists():
            try:
                data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
                for jid, jdict in data.items():
                    self._jobs[jid] = Job.from_dict(jdict)
            except Exception:
                pass


# Global singleton
job_store = JobStore()
