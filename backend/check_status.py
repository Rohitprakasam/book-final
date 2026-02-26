import json

with open("data/output/jobs.json", encoding="utf-8") as f:
    d = json.load(f)

job = d["92dcc3e8"]
print("=== JOB STATUS ===")
print(f"Status: {job['status']}")
print(f"Phase: {job['current_phase']}")
print(f"Progress: {job['progress_percentage']}%")
print(f"Message: {job['message']}")
print(f"Recoverable: {job.get('is_recoverable')}")
print(f"Resume Phase: {job.get('resume_phase')}")
print()
print("=== LAST 30 LOG LINES ===")
for entry in job["log_lines"][-30:]:
    msg = entry.get("message", "")
    src = entry.get("source", "")
    print(f"[{src}] {msg}")
