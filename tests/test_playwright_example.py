"""The example's acceptance checks must survive Python optimization.

These standard-library tests simulate producer/auditor outputs. They do not
execute Playwright or replace the separately documented real HTTP example.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


PROBE = Path(__file__).resolve().parents[1] / "examples/playwright-api/probe.py"
FIELDS = (
    "testcases", "unique_identities", "duplicate_records", "collision_groups",
    "cases_with_retry_metadata",
)
EXPECTED = {
    "default": (4, 2, 2, 2, 0),
    "prefixed": (4, 4, 0, 0, 0),
    "retry": (2, 2, 0, 0, 2),
    "final-failure": (1, 1, 0, 0, 0),
    "shards": (4, 4, 0, 0, 0),
    "overlap-control": (8, 4, 4, 4, 0),
}


def run_control(probe_path: Path, fault: str) -> None:
    """Execute the actual verifier, injecting one incorrect synthetic outcome."""
    spec = importlib.util.spec_from_file_location("playwright_probe", probe_path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    class FakeServer:
        server_port = 12345

        def __init__(self, *args):
            pass

        def serve_forever(self):
            pass

        def shutdown(self):
            pass

        def server_close(self):
            pass

    def producer(command, env, log):
        name = log.stem
        suite = ET.Element("testsuite")
        count = 1 if name == "final-failure" else 2 if name.startswith("shard") or name == "retry" else 4
        for index in range(count):
            case = ET.SubElement(suite, "testcase", classname="synthetic", name=f"{name}-{index}")
            if name == "retry" and fault != "missing-retry":
                ET.SubElement(case, "flakyFailure")
            if name == "final-failure" and fault != "missing-failure":
                ET.SubElement(case, "failure")
        if fault != "missing-report":
            Path(env["REPORT"]).write_bytes(ET.tostring(suite))
        if fault == "runner-exit" and name == "default":
            return 23
        return 1 if name == "final-failure" else 0

    def auditor(command, **kwargs):
        files = command[4:]
        name = "overlap-control" if len(files) == 3 else "shards" if len(files) == 2 else Path(files[0]).stem
        summary = dict(zip(FIELDS, EXPECTED[name]))
        summary["potential_hidden_failure_groups"] = 0
        diagnostics = []
        code = 1 if name in ("default", "overlap-control") else 0
        if name == "default":
            if fault == "audit-exit":
                code = 23
            elif fault == "counts":
                summary["collision_groups"] = 0
            elif fault == "diagnostics":
                diagnostics = [{"message": "synthetic diagnostic"}]
            elif fault == "hidden-failure":
                summary["potential_hidden_failure_groups"] = 1
            elif fault == "changed-xml":
                report = Path(files[0])
                report.write_bytes(report.read_bytes() + b" ")
        return subprocess.CompletedProcess(command, code, json.dumps({"summary": summary, "diagnostics": diagnostics}), "")

    with tempfile.TemporaryDirectory(prefix="probe-control-") as temporary:
        probe.ROOT = Path(temporary)
        probe.Handler.calls = [{"path": "/synthetic", "status": 200}] * (16 if fault == "http-count" else 17)
        with (
            patch.object(probe, "ThreadingHTTPServer", FakeServer),
            patch.object(probe, "run", producer),
            patch.object(probe.subprocess, "run", auditor),
            patch.object(sys, "argv", [str(probe_path), "--auditor-python", sys.executable]),
        ):
            probe.main()


class PlaywrightVerifierTests(unittest.TestCase):
    def test_outcomes_remain_checked_with_optimization(self):
        faults = (
            "valid", "runner-exit", "audit-exit", "counts", "diagnostics",
            "hidden-failure", "changed-xml", "missing-retry", "missing-failure",
            "http-count", "missing-report",
        )
        modes = (
            ("normal", [], None),
            ("-O", ["-O"], None),
            ("-OO", ["-OO"], None),
            ("environment-1", [], "1"),
            ("environment-2", [], "2"),
        )
        for mode, flags, optimization in modes:
            for fault in faults:
                with self.subTest(mode=mode, fault=fault):
                    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR") if key in os.environ}
                    if optimization is not None:
                        env["PYTHONOPTIMIZE"] = optimization
                    result = subprocess.run(
                        [sys.executable, *flags, str(Path(__file__).resolve()), "--probe-control", str(PROBE), fault],
                        capture_output=True, text=True, timeout=15, env=env,
                    )
                    if fault == "valid":
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(json.loads(result.stdout)["result"], "passed")
                    else:
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertNotIn('"result": "passed"', result.stdout)
                        self.assertIn("FileNotFoundError" if fault == "missing-report" else "RuntimeError", result.stderr)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--probe-control":
        run_control(Path(sys.argv[2]), sys.argv[3])
    else:
        unittest.main()
