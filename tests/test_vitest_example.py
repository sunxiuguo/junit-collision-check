"""The multi-project example audits identity independently of test outcomes."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET


class VitestProjectExampleTests(unittest.TestCase):
    def test_native_shape_controls(self):
        root = Path(__file__).resolve().parents[1]
        for name, code, cases, identities, groups in [
            ("default.xml", 1, 2, 1, 1),
            ("distinct.xml", 0, 2, 2, 0),
            ("distinct-failure.xml", 0, 4, 4, 0),
        ]:
            with self.subTest(name=name):
                fixture = root / "examples" / "vitest-projects" / name
                before = fixture.read_bytes()
                result = subprocess.run(
                    [sys.executable, "-m", "junit_collision_check", str(fixture),
                     "--format", "json"],
                    cwd=root, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["summary"]["testcases"], cases)
                self.assertEqual(report["summary"]["unique_identities"], identities)
                self.assertEqual(report["summary"]["collision_groups"], groups)
                self.assertEqual(fixture.read_bytes(), before)
        mixed = ET.parse(root / "examples/vitest-projects/distinct-failure.xml")
        self.assertEqual(len(mixed.findall(".//testcase/failure")), 1)
        self.assertEqual(len(mixed.findall(".//testcase/skipped")), 2)


if __name__ == "__main__":
    unittest.main()
