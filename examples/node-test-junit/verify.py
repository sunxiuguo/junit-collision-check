"""Verify the supported and rejected JUnit shapes from a real node:test runner."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
NODE_VERSION = "v24.22.3"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def run(command, *, cwd, env):
    return subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, timeout=15, check=False
    )


def write_test(path, suite, failing):
    body = f"test('smoke', () => assert.equal(1, {2 if failing else 1}));"
    statement = body if suite is None else f"describe({json.dumps(suite)}, () => {{ {body} }});"
    path.write_text(
        "import { describe, test } from 'node:test';\n"
        "import assert from 'node:assert/strict';\n"
        f"{statement}\n",
        encoding="utf-8",
    )


def report_for(node, files, path, *, cwd, env, expected):
    result = run([node, "--test", "--test-reporter=junit", *files], cwd=cwd, env=env)
    require(result.returncode == expected, f"{path.name}: unexpected Node exit {result.returncode}")
    require(result.stdout, f"{path.name}: no report from Node")
    path.write_bytes(result.stdout)
    return ET.fromstring(result.stdout)


def audit(paths, *, cwd, env, expected, diagnostic=None, gitlab=False):
    digests = [hashlib.sha256(path.read_bytes()).digest() for path in paths]
    args = ["--identity", "gitlab"] if gitlab else []
    result = run(
        [sys.executable, "-m", "junit_collision_check", "--format", "json", *args, *paths],
        cwd=cwd,
        env=env,
    )
    label = " + ".join(path.name for path in paths)
    require(result.returncode == expected, f"{label}: unexpected audit exit {result.returncode}")
    data = json.loads(result.stdout)
    require(
        digests == [hashlib.sha256(path.read_bytes()).digest() for path in paths],
        f"{label}: audit changed the report",
    )
    if diagnostic is not None:
        require(
            any(item["code"] == diagnostic for item in data["diagnostics"]),
            f"{label}: expected {diagnostic}",
        )
    return data


def main():
    node = shutil.which("node")
    require(node is not None, "Node 24.22.3 must be available on PATH")
    with tempfile.TemporaryDirectory(prefix="node-test-junit-") as scratch:
        work = Path(scratch)
        home = work / "home"
        home.mkdir()
        env = {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home),
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "NO_COLOR": "1",
            "PATH": os.defpath,
        }
        version = run([node, "--version"], cwd=work, env=env)
        require(
            version.returncode == 0 and version.stdout.decode().strip() == NODE_VERSION,
            f"This example expects Node {NODE_VERSION}",
        )
        files = [work / app / "smoke.test.mjs" for app in ("app-a", "app-b")]
        for file in files:
            file.parent.mkdir()

        # name, suites, failures, runner/default/GitLab/combined exit, generic collision count
        cases = (
            ("top-level", (None, None), (False, True), (1, 2, 2, 1), None),
            ("distinct-pass", ("app-a", "app-b"), (False, False), (0, 0, 0, 0), 0),
            ("distinct-mixed", ("app-a", "app-b"), (False, True), (1, 0, 2, 1), 0),
            ("shared-mixed", ("shared", "shared"), (False, True), (1, 1, 2, 1), 1),
            ("shared-pass", ("shared", "shared"), (False, False), (0, 1, 1, 1), 1),
        )
        for name, suites, failures, statuses, duplicates in cases:
            node_status, audit_status, gitlab_status, gate_status = statuses
            for file, suite, failing in zip(files, suites, failures, strict=True):
                write_test(file, suite, failing)
            report = work / f"{name}.xml"
            tree = report_for(node, files, report, cwd=work, env=env, expected=node_status)
            testcases = list(tree.iter("testcase"))
            require(len(testcases) == 2, f"{name}: expected two produced cases")
            classes = sorted(case.attrib["classname"] for case in testcases)
            require(classes == sorted(suite or "test" for suite in suites), f"{name}: wrong identities")
            actual_failures = sum(case.find("failure") is not None for case in testcases)
            require(actual_failures == sum(failures), f"{name}: wrong produced outcomes")

            diagnostic = None
            gitlab_diagnostic = None
            if suites == (None, None):
                require(tree.tag == "testsuites" and len(tree.findall("testcase")) == 2,
                        "expected direct testcase children of testsuites")
                split = [work / "split-a.xml", work / "split-b.xml"]
                for file, output, failing in zip(files, split, failures, strict=True):
                    report_for(node, [file], output, cwd=work, env=env, expected=int(failing))
                diagnostic = gitlab_diagnostic = "UNSUPPORTED_STRUCTURE"
                audit(split, cwd=work, env=env, expected=2, diagnostic=diagnostic)
            elif any(failures):
                require(any("failure" in case.attrib for case in testcases), "expected Node's failure attribute")
                gitlab_diagnostic = "UNSUPPORTED_GITLAB_PROFILE"

            data = audit([report], cwd=work, env=env, expected=audit_status, diagnostic=diagnostic)
            gitlab = audit([report], cwd=work, env=env, expected=gitlab_status,
                           diagnostic=gitlab_diagnostic, gitlab=True)
            if duplicates is not None:
                require(data["summary"]["testcases"] == 2, f"{name}: wrong parsed count")
                require(data["summary"]["collision_groups"] == duplicates,
                        f"{name}: wrong number of collisions")
                require(data["summary"]["potential_hidden_failure_groups"] == int(name == "shared-mixed"),
                        f"{name}: wrong mixed-outcome collision count")
            if gitlab_status != 2:
                require(gitlab["summary"]["testcases"] == 2, f"{name}: wrong GitLab profile count")
                require(gitlab["summary"]["collision_groups"] == duplicates,
                        f"{name}: wrong GitLab profile collision count")
            require((node_status or audit_status) == gate_status, f"{name}: wrong combined gate")
            print(f"{name}: node={node_status} audit={audit_status} gitlab={gitlab_status} gate={gate_status}")
        print("Verified five native Node report controls and the split-XML rejection.")


if __name__ == "__main__":
    main()
