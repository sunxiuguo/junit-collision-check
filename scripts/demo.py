"""Verify the public, offline broken/control demo with its expected exit codes."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
for name, expected, groups in [("retry-collision", 1, 1), ("unique-tests", 0, 0)]:
    result = subprocess.run(
        [sys.executable, "-m", "junit_collision_check", f"examples/{name}.xml", "--format", "json"],
        cwd=root, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["summary"]["collision_groups"] == groups, report
    print(f"{name}: expected exit {expected}, observed {result.returncode}; {groups} collision groups")
print("Offline demo verified")
