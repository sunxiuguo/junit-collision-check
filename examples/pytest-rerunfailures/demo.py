"""Verify real retry-plugin XML against the unchanged auditor; synthetic tests only."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

VERSIONS = ("16.4", "16.6", "16.6.1", "16.7")
FIXTURE = '''attempts = 0

def test_always_fails():
    assert False, "synthetic failure"

def test_eventually_passes():
    global attempts
    attempts += 1
    assert attempts >= 3, "synthetic retry"

def test_always_passes():
    assert True
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-version", required=True, choices=VERSIONS)
    version = parser.parse_args().plugin_version
    if importlib.metadata.version("pytest") != "9.1.1":
        parser.error("install pytest==9.1.1 for this pinned experiment")
    if importlib.metadata.version("pytest-rerunfailures") != version:
        parser.error("installed pytest-rerunfailures version does not match --plugin-version")
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="junit-retry-example-") as directory:
        work = Path(directory)
        (work / "test_retry.py").write_text(FIXTURE, encoding="utf-8")
        (work / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        # Keep only OS runtime essentials. Never inherit PYTEST_ADDOPTS, PYTHONPATH,
        # credentials, arbitrary plugin configuration or project configuration.
        env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
        env.update(HOME=str(work), USERPROFILE=str(work), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONNOUSERSITE="1")
        for test, retries in (("always_fails", 2), ("eventually_passes", 2), ("always_passes", 2), ("always_fails", 0)):
            report = work / f"{test}-{retries}.xml"
            runner = subprocess.run(
                [sys.executable, "-m", "pytest", "-p", "pytest_rerunfailures", "-c", str(work / "pytest.ini"), "--rootdir", str(work), "-q", f"test_retry.py::test_{test}", f"--reruns={retries}", f"--junitxml={report}"],
                cwd=work, env=env, capture_output=True, text=True, timeout=30,
            )
            expected_runner = int(test == "always_fails")
            if runner.returncode != expected_runner:
                raise AssertionError((test, runner.returncode, runner.stdout, runner.stderr))
            original = report.read_bytes()
            records = list(ET.fromstring(original).iter("testcase"))
            collides = version in ("16.6.1", "16.7") and retries == 2 and test != "always_passes"
            audit = subprocess.run(
                [sys.executable, str(root / "scripts/check_reports.py"), str(report), "--format", "json"],
                cwd=work, env=env, capture_output=True, text=True, timeout=30,
            )
            result = json.loads(audit.stdout)
            assert audit.returncode == int(collides), result
            assert len(records) == (3 if collides else 1), result
            assert result["summary"]["testcases"] == len(records), result
            assert result["summary"]["collision_groups"] == int(collides), result
            hidden = collides and test == "always_fails"
            assert result["summary"]["potential_hidden_failure_groups"] == int(hidden), result
            assert sum(case.find("failure") is not None for case in records) == expected_runner
            if collides:
                assert result["collisions"][0]["code"] == ("CONFLICTING_OUTCOMES" if hidden else "DUPLICATE_IDENTITY")
            assert hashlib.sha256(report.read_bytes()).digest() == hashlib.sha256(original).digest()
            print(f"{version} {test} reruns={retries}: pytest={runner.returncode}, records={len(records)}, audit={audit.returncode}")
    print("Four expected example outcomes verified; this is not a production test gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
