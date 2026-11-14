"""Synthetic producer-phase boundary; not a production test-runner wrapper."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PHASE = '''import pytest
@pytest.fixture
def cleanup():
    yield
    assert False, "synthetic teardown error"
def test_phase(cleanup):
    assert False, "synthetic call failure"
'''
DISTINCT = '''import pytest
@pytest.fixture
def cleanup(value):
    yield
    if value == 2:
        assert False, "synthetic teardown error"
@pytest.mark.parametrize("value", [1, 2])
def test_distinct(value, record_xml_attribute, cleanup):
    record_xml_attribute("name", "test_phase")
    record_xml_attribute("classname", "test_phase")
    if value == 1:
        assert False, "synthetic call failure"
'''


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    import pytest
    require(pytest.__version__ == "9.1.1", "Install the pinned pytest 9.1.1 example dependency")
    env = os.environ.copy()
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(key, None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONPATH"] = str(ROOT)
    results = {}
    with tempfile.TemporaryDirectory(prefix="pytest-phase-example-") as temp:
        work = Path(temp)
        (work / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        for label, source, family, code, outcomes in (
            ("phase", PHASE, "xunit2", "CONFLICTING_OUTCOMES", ["failure", "error"]),
            ("distinct", DISTINCT, "xunit1", "CONFLICTING_OUTCOMES", ["failure", "error"]),
        ):
            (work / "test_sample.py").write_text(source, encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "pytest", "test_sample.py", "-q", "-c", "pytest.ini", "--rootdir", temp, "--noconftest", "-p", "no:cacheprovider", "-o", f"junit_family={family}", "--junitxml", "report.xml"], cwd=work, env=env, capture_output=True, text=True, timeout=30)
            require(run.returncode == 1, f"{label}: expected synthetic test failure")
            cases = list(ET.parse(work / "report.xml").iter("testcase"))
            require(len(cases) == 2, f"{label}: expected two testcase records")
            require({(c.get("classname"), c.get("name")) for c in cases} == {("test_sample" if label == "phase" else "test_phase", "test_phase")}, f"{label}: identity changed")
            require([[child.tag for child in c] for c in cases] == [[x] for x in outcomes], f"{label}: outcomes changed")
            audit = subprocess.run([sys.executable, "-m", "junit_collision_check", "report.xml", "--format", "json"], cwd=work, env=env, capture_output=True, text=True, timeout=30)
            report = json.loads(audit.stdout)
            require(audit.returncode == 1, f"{label}: auditor should retain collision")
            require(len(report["collisions"]) == 1 and report["collisions"][0]["code"] == code, f"{label}: collision classification changed")
            require(not report["collisions"][0]["potential_hidden_failure"], f"{label}: both outcomes are failing")
            results[label] = {"pytest_exit": run.returncode, "auditor_exit": audit.returncode, "records": len(cases), "classification": code}
    print(json.dumps({"pytest": pytest.__version__, "synthetic_only": True, "results": results}, indent=2))


if __name__ == "__main__":
    main()
