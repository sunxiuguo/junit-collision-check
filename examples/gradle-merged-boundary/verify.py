"""Verify the documented post-merge boundary without third-party dependencies."""
from pathlib import Path
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
fixture = Path(__file__).with_name("merged.xml")
before = fixture.read_bytes()
run = subprocess.run(
    [sys.executable, "-m", "junit_collision_check", str(fixture), "--format", "json"],
    cwd=root, capture_output=True, text=True, check=False,
)
report = json.loads(run.stdout)
assert run.returncode == 0, (run.returncode, run.stderr)
assert report["status"] == "clean", report
assert report["summary"]["testcases"] == 1, report
assert report["summary"]["collision_groups"] == 0, report
assert report["summary"]["cases_with_retry_metadata"] == 1, report
assert fixture.read_bytes() == before
print("Verified: no duplicate records remain; retry metadata is not collision proof.")
