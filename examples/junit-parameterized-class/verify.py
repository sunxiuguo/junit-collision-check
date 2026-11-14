#!/usr/bin/env python3
"""Generate real legacy JUnit XML from original synthetic tests; download nothing."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERSIONS = {
    "6.0.3": "3ba0d6150af79214a1411f9ea2fbef864eef68b68c89a17f672c0b89bff9d3a2",
    "6.1.3": "e62b96ac475dbcde8599ea905d088f65d90778f86e259b856a49fa5c4ea256ec",
}


def run(command, cwd):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)


def verify(jars, java):
    # Check BOTH inputs before executing either artifact. No dynamic dependencies.
    for version, expected in VERSIONS.items():
        actual = hashlib.sha256(jars[version].read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"JUnit {version}: JAR SHA-256 mismatch; nothing executed")
    with tempfile.TemporaryDirectory(prefix="junit-identity-demo-") as temp:
        work = Path(temp)
        for version in VERSIONS:
            classes = work / f"classes-{version}"
            reports = work / f"reports-{version}"
            classes.mkdir()
            reports.mkdir()
            jar = str(jars[version])
            compiled = run([java, "-m", "jdk.compiler/com.sun.tools.javac.Main",
                            "-cp", jar, "-d", str(classes), str(HERE / "BatchSizeTest.java")], work)
            if compiled.returncode:
                raise RuntimeError(f"JUnit {version}: compilation failed; use a full JDK 17+\n{compiled.stderr}")
            tested = run([java, "-jar", jar, "execute", "-cp", str(classes),
                          "--select-class", "BatchSizeTest", "--include-engine", "junit-jupiter",
                          "--reports-dir", str(reports), "--disable-banner"], work)
            if tested.returncode:
                raise RuntimeError(f"JUnit {version}: runner exit {tested.returncode}; not an audit success")
            report = reports / "TEST-junit-jupiter.xml"
            cases = list(ET.parse(report).iter("testcase"))
            if len(cases) != 6 or any(c.find(tag) is not None for c in cases
                                      for tag in ("failure", "error", "skipped")):
                raise RuntimeError(f"JUnit {version}: expected six successful synthetic tests")
            audited = run([sys.executable, "-m", "junit_collision_check", str(report),
                           "--format", "json"], ROOT)
            result = json.loads(audited.stdout)
            summary = result["summary"]
            old = version == "6.0.3"
            expected = {"testcases": 6, "unique_identities": 2 if old else 6,
                        "collision_groups": 2 if old else 0,
                        "duplicate_records": 4 if old else 0,
                        "potential_hidden_failure_groups": 0}
            if (audited.returncode != (1 if old else 0)
                    or result["status"] != ("issues" if old else "clean")
                    or any(summary[k] != value for k, value in expected.items())):
                raise RuntimeError(f"JUnit {version}: unexpected audit result: {result}")
            print(json.dumps({"junit": version, "runner_exit": tested.returncode,
                              "audit_exit": audited.returncode, **expected}, sort_keys=True))
    print("PASS: historical collision reproduced; fixed-version control is clean.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar-6-0-3", required=True, type=Path)
    parser.add_argument("--jar-6-1-3", required=True, type=Path)
    parser.add_argument("--java", default="java", help="Java executable from a full JDK 17+")
    args = parser.parse_args()
    try:
        verify({"6.0.3": args.jar_6_0_3.resolve(), "6.1.3": args.jar_6_1_3.resolve()}, args.java)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, ET.ParseError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
