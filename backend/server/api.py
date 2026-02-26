"""
BookUdecate V1.0 — FastAPI Backend Server
=======================================
Provides a REST + SSE API for the BookUdecate pipeline.
Allows frontend clients to:
  - Submit PDF generation jobs
  - Stream real-time progress via SSE
  - Poll logs
  - Download the final PDF

Run with:
    uvicorn server.api:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
    POST   /api/v1/generate                  → Submit a new job
    GET    /api/v1/jobs/{job_id}/progress    → SSE stream of progress events
    GET    /api/v1/jobs/{id}/logs            → Paginated logs
    GET    /api/v1/jobs/{id}/download        → Download final PDF
    GET    /api/v1/jobs/{id}                 → Job status snapshot
    GET    /api/v1/jobs                      → All jobs
"""

from __future__ import annotations
from server.sse_manager import sse_manager
from server.jobs import job_store, Job

import os
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

# Import local modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

app = FastAPI(
    title="BookUdecate V1.0 API",
    description="AI-powered textbook generation pipeline",
    version="1.0.0",
)


# ──────────────────────────────────────────────
# STARTUP ACTIONS
# ──────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """On startup, mark any 'processing' jobs as failed/interrupted."""
    for job in job_store._jobs.values():
        if job.status == "processing":
            job_store.update(
                job.job_id,
                status="failed",
                message="Job interrupted by server restart. You can resume.",
                is_recoverable=True,
                resume_phase=job.current_phase,
            )
    job_store._save()
    print("🚀 Server startup: Recovered interrupted jobs.")


# ──────────────────────────────────────────────
# CORS — Allow Vite dev servers
# ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)

OUTPUT_DIR = Path("data/output")
BASE_DIR = Path(__file__).resolve().parent.parent


# ──────────────────────────────────────────────
# C1: POST /api/v1/generate — Submit Job
# ──────────────────────────────────────────────
@app.post("/api/v1/generate")
async def generate(
    pdf_file: Optional[UploadFile] = File(None),
    book_subject: str = Form("Engineering"),
    book_persona: str = Form("Senior Engineering Professor"),
    academic_level: str = Form("Undergraduate"),
    target_pages: int = Form(600),
    max_new_diagrams: int = Form(40),
    skip_images: bool = Form(False),
    provider: str = Form("gemini"),
    ollama_url: str = Form("http://localhost:11434"),
    job_id: Optional[str] = Form(None),  # For resume
    resume_phase: Optional[int] = Form(None),  # For resume
) -> JSONResponse:
    """
    Submit a new book generation job, or resume an existing one.
    Returns { job_id, status, message } immediately (202 Accepted).
    Progress is streamed via SSE at /jobs/{id}/progress.
    """
    config = {
        "book_subject": book_subject,
        "book_persona": book_persona,
        "academic_level": academic_level,
        "target_pages": target_pages,
        "max_new_diagrams": max_new_diagrams,
        "skip_images": skip_images,
        "provider": provider,
        "ollama_url": ollama_url,
    }

    # Resume case: use existing job_id
    if resume_phase and job_id:
        job = job_store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        job_store.update(
            job_id,
            status="processing",
            resume_phase=resume_phase,
            is_recoverable=False,
            message=f"Resuming from Phase {resume_phase}...",
        )
    else:
        # New job
        job = job_store.create(config=config)
        job_id = job.job_id

        # Save uploaded PDF
        if pdf_file:
            upload_path = OUTPUT_DIR / f"input_{job_id}.pdf"
            upload_path.parent.mkdir(parents=True, exist_ok=True)
            content = await pdf_file.read()
            upload_path.write_bytes(content)
        else:
            raise HTTPException(status_code=400, detail="No PDF file provided")

    import asyncio

    loop = asyncio.get_running_loop()

    # Launch pipeline in a background thread (non-blocking)
    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, config, resume_phase, loop),
        daemon=True,
        name=f"pipeline-{job_id}",
    )
    thread.start()

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "processing", "message": "Job started"},
    )


# ──────────────────────────────────────────────
# C2: GET /api/v1/jobs/{id}/progress — SSE Stream
# ──────────────────────────────────────────────
@app.get("/api/v1/jobs/{job_id}/progress")
async def progress_stream(job_id: str, request: Request) -> EventSourceResponse:
    """
    Server-Sent Events stream for real-time job progress.
    Events: { progress_percentage, current_phase, status, message }
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    import json

    async def event_generator():
        # Send current state immediately on connect
        yield {
            "data": json.dumps(_job_progress_payload(job)),
            "event": "message",
            "id": f"{job_id}-0",
        }

        # Stream future events
        async for event in sse_manager.subscribe(job_id):
            if await request.is_disconnected():
                break
            yield {
                "data": json.dumps(event),
                "event": "message",
                "id": f"{job_id}-{event.get('progress_percentage', 0)}",
            }

    return EventSourceResponse(event_generator())


# ──────────────────────────────────────────────
# GET /api/v1/jobs/{id} — Status Snapshot
# ──────────────────────────────────────────────
@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _job_progress_payload(job)


# ──────────────────────────────────────────────
# C3: GET /api/v1/jobs/{id}/logs — Log Polling
# ──────────────────────────────────────────────
@app.get("/api/v1/jobs/{job_id}/logs")
async def get_logs(job_id: str, cursor: int = 0, limit: int = 50) -> dict:
    """
    Return paginated log lines. Poll every 3 seconds from frontend.
    cursor = index of last seen line. Returns new lines after cursor.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    all_lines = job.log_lines
    new_lines = all_lines[cursor : cursor + limit]
    return {
        "job_id": job_id,
        "logs": new_lines,
        "next_cursor": str(cursor + len(new_lines)),
        "total": len(all_lines),
        "has_more": (cursor + len(new_lines)) < len(all_lines),
    }


# ──────────────────────────────────────────────
# GET /api/v1/jobs/{id}/download — Download PDF
# ──────────────────────────────────────────────
@app.get("/api/v1/jobs/{job_id}/download")
async def download_pdf(job_id: str) -> FileResponse:
    """Download the final compiled PDF for a completed job."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job.status != "completed":
        raise HTTPException(
            status_code=409, detail=f"Job is not completed (status: {job.status})"
        )

    pdf_path = Path(job.pdf_path) if job.pdf_path else OUTPUT_DIR / "BookEducate.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on server")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"BookUdecate_{job_id}.pdf",
    )


# ──────────────────────────────────────────────
# GET /api/v1/jobs — All Jobs
# ──────────────────────────────────────────────
@app.get("/api/v1/jobs")
async def list_jobs() -> dict:
    return {"jobs": job_store.all_jobs()}


# ──────────────────────────────────────────────
# BACKGROUND PIPELINE RUNNER
# ──────────────────────────────────────────────
def _run_pipeline(job_id: str, config: dict, resume_phase: Optional[int], loop=None):
    """
    Runs the BookUdecate pipeline in a background thread.
    Publishes SSE events via sse_manager after each phase completes.
    """
    import subprocess
    import json
    import re
    import time

    def emit(
        progress: float,
        phase: int,
        status: str,
        message: str,
        eta_phase: int | None = None,
        eta_total: int | None = None,
    ):
        update_kwargs = {
            "progress_percentage": progress,
            "current_phase": phase,
            "status": status,
            "message": message,
        }
        if eta_phase is not None:
            update_kwargs["eta_phase_seconds"] = eta_phase
        if eta_total is not None:
            update_kwargs["eta_total_seconds"] = eta_total

        job = job_store.update(job_id, **update_kwargs)
        job_store.append_log(job_id, message, level="INFO", source=f"Phase {phase}")
        job_store._save()  # Ensure progress is persisted to disk!
        if job and loop and loop.is_running():
            import asyncio

            asyncio.run_coroutine_threadsafe(
                sse_manager.publish(job_id, _job_progress_payload(job)), loop
            )

    try:
        job_store.update(job_id, status="processing")
        start_phase = resume_phase or 1
        current_active_phase = start_phase  # Initialize early for scoping
        phase_start_time = time.time()
        input_pdf = str(OUTPUT_DIR / f"input_{job_id}.pdf")

        # Set env vars for this job
        env = os.environ.copy()
        env["MAX_NEW_DIAGRAMS"] = str(config.get("max_new_diagrams", 40))
        env["BOOK_SUBJECT"] = config.get("book_subject", "Engineering")
        env["BOOK_PERSONA"] = config.get("book_persona", "Senior Engineering Professor")
        env["ACADEMIC_LEVEL"] = config.get("academic_level", "Undergraduate")
        env["TARGET_PAGES"] = str(config.get("target_pages", 600))
        env["LLM_PROVIDER"] = config.get("provider", "gemini")
        env["OLLAMA_API_BASE"] = config.get("ollama_url", "http://localhost:11434")
        if config.get("skip_images"):
            env["SKIP_IMAGES"] = "true"
            env["MAX_NEW_DIAGRAMS"] = "0"

        PHASE_DISPLAY_LABELS = {
            1: "Phase 1: Deconstructing PDF",
            2: "Phase 2: Expanding Content (LLM Swarm)",
            3: "Phase 3: Generating AI Diagrams",
            4: "Phase 4: Structuring & Compiling PDF",
        }

        # Use a single process execution - main.py cascades naturally
        cmd = [
            sys.executable,
            "-u",
            "main.py",
            "--phase",
            str(start_phase),
        ]
        if resume_phase is not None:
            cmd.append("--is-resume")
            
        if start_phase <= 1:
            cmd.append(input_pdf)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(BASE_DIR),
            env=env,
        )

        progress_regex = re.compile(
            r"(?:Chunk|section|Page|Image) (\d+)/(\d+)", re.IGNORECASE
        )

        # Emit initial progress for resumes to avoid 0% flash
        if start_phase > 1:
            emit(
                progress=(start_phase - 1) * 25.0,
                phase=start_phase,
                status="processing",
                message=f"Resuming {PHASE_DISPLAY_LABELS.get(start_phase, 'Pipeline')}...",
            )

        # Stream stdout line-by-line in real time
        for line in iter(process.stdout.readline, ""):
            line = line.strip("\r\n")
            if not line:
                continue

            # ── Dynamic Phase Detection ──
            # Watch for engine phase transitions in logs to keep UI sync'd
            if "PHASE 2" in line.upper() or "SKIPPING TO PHASE 2" in line.upper():
                current_active_phase = 2
                phase_start_time = time.time()
            elif "PHASE 3" in line.upper() or "SKIPPING TO PHASE 3" in line.upper() or "RESOLVING AI DIAGRAMS" in line.upper():
                current_active_phase = 3
                phase_start_time = time.time()
            elif "PHASE 4" in line.upper() or "SKIPPING TO PHASE 4" in line.upper() or "AI STRUCTURING" in line.upper():
                current_active_phase = 4
                phase_start_time = time.time()

            # Detect level for logging
            level = "INFO"
            if "ERROR" in line.upper():
                level = "ERROR"
            elif "WARN" in line.upper():
                level = "WARN"

            job_store.append_log(
                job_id, line, level=level, source=f"Phase {current_active_phase}"
            )

            # Check for progress markers to calculate ETA
            m = progress_regex.search(line)
            if m:
                current = int(m.group(1))
                total = int(m.group(2))
                if current > 0 and total > 0:
                    elapsed = time.time() - phase_start_time
                    time_per_item = elapsed / current
                    remaining_items = total - current
                    eta_seconds = int(time_per_item * remaining_items)

                    # Calculate smooth progress within the 25% phase block
                    # Phase 1: 0-25, Phase 2: 25-50, Phase 3: 50-75, Phase 4: 75-100
                    base_prog = (current_active_phase - 1) * 25.0
                    phase_prog = (current / total) * 25.0
                    total_prog = min(base_prog + phase_prog, base_prog + 24.9)

                    # Project total ETA
                    total_eta_seconds = (
                        int((eta_seconds / 25.0) * (100.0 - total_prog))
                        if total_prog > 0
                        else None
                    )

                    mins, secs = divmod(eta_seconds, 60)
                    eta_str = f"ETA: {mins}m {secs}s"

                    emit(
                        progress=round(total_prog, 1),
                        phase=current_active_phase,
                        status="processing",
                        message=f"{PHASE_DISPLAY_LABELS.get(current_active_phase, 'Processing')} — {current}/{total} — Phase {eta_str}",
                        eta_phase=eta_seconds,
                        eta_total=total_eta_seconds,
                    )
            else:
                # Still emit every line for logs, but keep previous progress
                job = job_store.get(job_id)
                if job:
                    emit(
                        progress=job.progress_percentage,
                        phase=current_active_phase,
                        status="processing",
                        message=line[:100],  # Use line as brief status
                    )

        process.wait()

        if process.returncode != 0:
            job = job_store.get(job_id)
            current_p = job.current_phase if job else current_active_phase
            emit(
                progress=(current_p - 1) * 25.0,
                phase=current_p,
                status="failed",
                message=f"Pipeline failed at Phase {current_p}.",
            )
            job_store.update(job_id, is_recoverable=True, resume_phase=current_p)
            job_store._save()
            return

        # All phases done
        pdf_path = str(OUTPUT_DIR / "BookEducate.pdf")
        job_store.update(
            job_id,
            status="completed",
            progress_percentage=100.0,
            pdf_path=pdf_path,
            message="Book generation complete! PDF is ready to download.",
        )
        job_store._save()
        emit(100.0, 4, "completed", "BookUdecate complete! PDF ready.")

    except subprocess.TimeoutExpired:
        emit(0, 0, "failed", "Pipeline timed out after 2 hours.")
        job_store.update(job_id, is_recoverable=True)
        job_store._save()
    except Exception as e:
        emit(0, 0, "failed", f"Unexpected error: {str(e)[:200]}")
        job_store.update(job_id, is_recoverable=True)
        job_store._save()


def _job_progress_payload(job: Job) -> dict:
    # Map the numeric phase to a descriptive label for the UI
    labels = {
        1: "Phase 1: Deconstructing",
        2: "Phase 2: Expanding Content",
        3: "Phase 3: AI Diagrams",
        4: "Phase 4: Compiling PDF",
    }

    payload = {
        "job_id": job.job_id,
        "status": job.status,
        "progress_percentage": job.progress_percentage,
        "current_phase": labels.get(job.current_phase, "Initializing"),
        "current_task": job.message,  # Map backend 'message' to frontend 'current_task'
        "message": job.message,  # Keep original for compatibility
        "is_recoverable": job.is_recoverable,
        "resume_phase": job.resume_phase,
        "eta_phase_seconds": job.eta_phase_seconds,
        "eta_total_seconds": job.eta_total_seconds,
    }

    if job.status == "failed":
        payload["error"] = {
            "code": (
                "JOB_FAILED"
                if job.message != "Job interrupted by server restart. You can resume."
                else "SERVER_INTERRUPTED"
            ),
            "phase_failed_in": labels.get(job.current_phase, "Pipeline"),
            "message": job.message,
            "is_recoverable": job.is_recoverable,
            "resume_phase": job.resume_phase,
        }

    return payload
