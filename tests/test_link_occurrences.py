"""Independently authored synthetic link-occurrence identity regressions.

These tests audit XML only. They do not run lychee or a CI report consumer.
"""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from junit_collision_check import inspect_reports, parse_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "link-occurrence"
BEFORE = FIXTURES / "repeated-link-before.xml"
AFTER = FIXTURES / "repeated-link-after.xml"


def audit(path, **kwargs):
    return inspect_reports([(path.name, io.BytesIO(path.read_bytes()))], **kwargs)


class LinkOccurrenceTests(unittest.TestCase):
    def test_file_attributes_do_not_disambiguate_default_identity(self):
        result = audit(BEFORE)
        self.assertEqual(result["status"], "issues")
        self.assertEqual(result["summary"]["testcases"], 2)
        self.assertEqual(result["summary"]["unique_identities"], 1)
        self.assertEqual(result["summary"]["collision_groups"], 1)
        self.assertEqual(result["summary"]["duplicate_records"], 1)
        collision = result["collisions"][0]
        self.assertEqual(collision["code"], "DUPLICATE_IDENTITY")
        self.assertEqual(collision["identity"]["classname"], "")
        self.assertEqual(collision["identity"]["name"], "Failed https://example.invalid/retired")
        self.assertFalse(collision["potential_hidden_failure"])
        self.assertEqual([item["status"] for item in collision["occurrences"]], ["failure", "failure"])
        self.assertEqual([item["testcase"] for item in collision["occurrences"]], [1, 2])

    def test_same_report_and_suite_cannot_be_fixed_with_scope_switch(self):
        for options in ({"scope": "file"}, {"identity": "suite-class-name"}):
            with self.subTest(options=options):
                self.assertEqual(audit(BEFORE, **options)["status"], "issues")

    def test_unique_occurrence_names_are_clean_but_tests_still_failed(self):
        result = audit(AFTER)
        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["summary"]["testcases"], 2)
        self.assertEqual(result["summary"]["unique_identities"], 2)
        self.assertEqual(result["collisions"], [])
        cases, _ = parse_report(io.BytesIO(AFTER.read_bytes()), AFTER.name)
        self.assertEqual([item.status for item in cases], ["failure", "failure"])

    def test_cli_audit_gate_and_input_preservation(self):
        for path, expected_exit, expected_status in (
            (BEFORE, 1, "issues"), (AFTER, 0, "clean")
        ):
            with self.subTest(path=path.name):
                before_digest = hashlib.sha256(path.read_bytes()).digest()
                result = subprocess.run(
                    [sys.executable, "-m", "junit_collision_check", str(path), "--format", "json"],
                    cwd=ROOT, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, expected_exit)
                self.assertEqual(result.stderr, "")
                self.assertEqual(json.loads(result.stdout)["status"], expected_status)
                self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), before_digest)


if __name__ == "__main__":
    unittest.main()
