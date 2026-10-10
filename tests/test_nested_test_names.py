"""Synthetic output-shape tests; no Expecto or CI consumer execution."""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from junit_collision_check import inspect_reports, parse_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "nested-test-names"
BEFORE = FIXTURES / "truncated-before.xml"
AFTER = FIXTURES / "unique-after.xml"
SINGLE = FIXTURES / "single-truncated.xml"
PRIVATE_DETAIL = "SYNTHETIC_FAILURE_PRIVATE_DETAIL"


def audit(path, **kwargs):
    return inspect_reports([(path.name, io.BytesIO(path.read_bytes()))], **kwargs)


class NestedTestNameTests(unittest.TestCase):
    def test_truncated_sibling_names_collide_with_missing_classname(self):
        result = audit(BEFORE)
        self.assertEqual(result["status"], "issues")
        self.assertEqual(result["summary"]["testcases"], 2)
        self.assertEqual(result["summary"]["unique_identities"], 1)
        self.assertEqual(result["summary"]["collision_groups"], 1)
        self.assertEqual(result["summary"]["duplicate_records"], 1)
        collision = result["collisions"][0]
        self.assertEqual(collision["identity"], {"classname": "", "name": "[a; b; c; ... ]"})
        self.assertEqual(collision["code"], "CONFLICTING_OUTCOMES")
        self.assertEqual(collision["outcomes"], ["failure", "passed"])
        self.assertTrue(collision["potential_hidden_failure"])
        self.assertEqual([x["testcase"] for x in collision["occurrences"]], [1, 2])
        self.assertEqual([x["line"] for x in collision["occurrences"]], [5, 6])

    def test_scope_options_do_not_recover_lost_name_segments(self):
        for options in ({}, {"scope": "file"}, {"identity": "suite-class-name"},
                        {"scope": "file", "identity": "suite-class-name"}):
            with self.subTest(options=options):
                self.assertEqual(audit(BEFORE, **options)["status"], "issues")

    def test_full_sibling_names_are_unique_and_preserve_test_failure(self):
        result = audit(AFTER)
        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["summary"]["testcases"], 2)
        self.assertEqual(result["summary"]["unique_identities"], 2)
        before, _ = parse_report(io.BytesIO(BEFORE.read_bytes()), BEFORE.name)
        after, _ = parse_report(io.BytesIO(AFTER.read_bytes()), AFTER.name)
        self.assertEqual([x.status for x in before], ["failure", "passed"])
        self.assertEqual([x.status for x in after], [x.status for x in before])

    def test_same_outcome_name_loss_is_still_a_collision(self):
        source = BEFORE.read_bytes().replace(
            b'<failure message="SYNTHETIC_FAILURE_PRIVATE_DETAIL" />', b'')
        result = inspect_reports([("all-passed.xml", io.BytesIO(source))])
        collision = result["collisions"][0]
        self.assertEqual(result["status"], "issues")
        self.assertEqual(collision["code"], "DUPLICATE_IDENTITY")
        self.assertFalse(collision["potential_hidden_failure"])

    def test_single_truncated_name_is_clean_under_collision_only_contract(self):
        result = audit(SINGLE)
        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["summary"]["testcases"], 1)
        self.assertEqual(result["summary"]["unique_identities"], 1)

    def test_cli_exits_and_report_privacy_without_changing_inputs(self):
        for path, expected_exit, expected_status in (
            (BEFORE, 1, "issues"), (AFTER, 0, "clean"), (SINGLE, 0, "clean")
        ):
            for output_format in ("json", "text"):
                with self.subTest(path=path.name, output_format=output_format):
                    before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                    result = subprocess.run(
                        [sys.executable, "-m", "junit_collision_check", str(path),
                         "--format", output_format],
                        cwd=ROOT, capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, expected_exit)
                    self.assertEqual(result.stderr, "")
                    self.assertNotIn(PRIVATE_DETAIL, result.stdout + result.stderr)
                    if output_format == "json":
                        self.assertEqual(json.loads(result.stdout)["status"], expected_status)
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before_hash)


if __name__ == "__main__":
    unittest.main()
