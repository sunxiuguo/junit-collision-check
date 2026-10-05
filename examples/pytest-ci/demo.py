"""Verify collision and runner gates using real pytest-generated JUnit XML.

This runs only the synthetic test defined below, in a temporary directory. It is
an example self-test, not a wrapper for running a project's production tests.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_SENTINEL = "junit-demo-environment-must-not-appear-in-reports"
TEST_SOURCE = '''import os

def test_shared():
    fail_requested = os.environ.get("JUNIT_DEMO_FAIL") == "1"
    # Assert a local boolean so pytest never expands os.environ in failure XML.
    assert not fail_requested, "intentional demo failure"

def test_other():
    assert 2 + 2 == 4
'''


def require(condition, message):
    # Do not rely on assert: the example must also verify under python -O.
    if not condition:
        raise RuntimeError(message)


def run_pytest(directory, report_name, *, fail=False, test="test_shared"):
    report = directory / report_name
    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_PLUGINS", None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["JUNIT_DEMO_FAIL"] = "1" if fail else "0"
    env["JUNIT_DEMO_PRIVATE_SENTINEL"] = PRIVATE_SENTINEL
    result = subprocess.run(
        [sys.executable, "-m", "pytest", f"test_sample.py::{test}", "-q",
         "-c", "pytest.ini", "--rootdir", str(directory), "--noconftest",
         "-p", "no:cacheprovider", "-o", f"junit_suite_name={report.stem}",
         "--junitxml", str(report)],
        cwd=directory, env=env, capture_output=True, text=True, timeout=30,
    )
    require(result.returncode == (1 if fail else 0),
            f"Unexpected pytest exit {result.returncode}:\n{result.stdout}\n{result.stderr}")
    require(report.is_file(), "pytest did not produce the requested report")
    report_text = report.read_text(encoding="utf-8")
    require(PRIVATE_SENTINEL not in report_text,
            "pytest exposed the synthetic environment sentinel in a report")
    # pytest may abbreviate the middle of a large environment representation,
    # hiding the sentinel while still disclosing other values.
    require("environ({" not in report_text,
            "pytest expanded the process environment in a report")
    return report, result.returncode


def audit(paths):
    before = [hashlib.sha256(path.read_bytes()).digest() for path in paths]
    result = subprocess.run(
        [sys.executable, "-m", "junit_collision_check",
         *map(str, paths), "--format", "json"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    require(result.returncode in (0, 1),
            f"Audit failed to inspect the example: {result.stdout}\n{result.stderr}")
    require(before == [hashlib.sha256(path.read_bytes()).digest() for path in paths],
            "Audit changed an input report")
    return result.returncode, json.loads(result.stdout)


def verify_case(label, runner_exits, paths, *, expected_audit, expected_groups,
                expected_gate, expected_hidden=0, expected_code=None):
    audit_exit, report = audit(paths)
    require(audit_exit == expected_audit, f"{label}: unexpected audit exit {audit_exit}")
    require(report["summary"]["parsed_files"] == len(paths),
            f"{label}: unexpected parsed file count")
    require(report["summary"]["testcases"] == len(paths),
            f"{label}: expected exactly one selected test per report")
    require(report["summary"]["collision_groups"] == expected_groups,
            f"{label}: unexpected collision count")
    require(report["summary"]["potential_hidden_failure_groups"] == expected_hidden,
            f"{label}: unexpected hidden-failure risk count")
    combined_gate = 0 if all(code == 0 for code in runner_exits) and audit_exit == 0 else 1
    require(combined_gate == expected_gate, f"{label}: a failure was lost")
    if expected_code:
        require([item["code"] for item in report["collisions"]] == [expected_code],
                f"{label}: unexpected collision kind")
    print(json.dumps({"case": label, "pytest_exits": runner_exits,
                      "audit_exit": audit_exit, "combined_gate": combined_gate,
                      "collision_groups": expected_groups,
                      "potential_hidden_failure_groups": expected_hidden}))


def main():
    try:
        import pytest
    except ImportError:
        print("Install the optional examples/pytest-ci/requirements.txt first", file=sys.stderr)
        return 2
    print(f"Producer: pytest {pytest.__version__}")
    with tempfile.TemporaryDirectory(prefix="junit-pytest-demo-") as temporary:
        directory = Path(temporary)
        (directory / "test_sample.py").write_text(TEST_SOURCE, encoding="utf-8")
        (directory / "pytest.ini").write_text("[pytest]\njunit_family = xunit2\n", encoding="utf-8")
        passing_a, pass_a_exit = run_pytest(directory, "passing-a.xml")
        passing_b, pass_b_exit = run_pytest(directory, "passing-b.xml")
        other, other_exit = run_pytest(directory, "other.xml", test="test_other")
        failing, fail_exit = run_pytest(directory, "failing.xml", fail=True)

        verify_case("disjoint-shards", [pass_a_exit, other_exit], [passing_a, other],
                    expected_audit=0, expected_groups=0, expected_gate=0)
        verify_case("unique-failing", [fail_exit], [failing],
                    expected_audit=0, expected_groups=0, expected_gate=1)
        verify_case("overlapping-shards", [pass_a_exit, pass_b_exit], [passing_a, passing_b],
                    expected_audit=1, expected_groups=1, expected_gate=1,
                    expected_code="DUPLICATE_IDENTITY")
        verify_case("conflicting-retry", [fail_exit, pass_a_exit], [failing, passing_a],
                    expected_audit=1, expected_groups=1, expected_hidden=1,
                    expected_gate=1, expected_code="CONFLICTING_OUTCOMES")
    print("Expected example outcomes verified; this is not a production test gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
