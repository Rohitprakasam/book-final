import json
from pathlib import Path

JOBS_FILE = Path("data/output/jobs.json")
if JOBS_FILE.exists():
    with open(JOBS_FILE, "r", encoding="utf-8") as f:
        jobs = json.load(f)
    
    if "92dcc3e8" in jobs:
        job = jobs["92dcc3e8"]
        job["status"] = "failed"
        job["current_phase"] = 3
        job["resume_phase"] = 4
        job["message"] = "Corrected state: Ready to resume at Phase 4."
        job["is_recoverable"] = True
        
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)
        print("✅ Corrected job 92dcc3e8 state in jobs.json")
    else:
        print("❌ Job 92dcc3e8 not found in jobs.json")
else:
    print("❌ jobs.json not found")
