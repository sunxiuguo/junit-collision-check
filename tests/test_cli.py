import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import tomllib

from junit_collision_check.cli import render_text
from junit_collision_check import inspect_reports
from test_core import case, suite
import io

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'junit_collision_check', *args],
                              cwd=ROOT, capture_output=True, text=True, timeout=10)

    def test_demo_exit_codes(self):
        self.assertEqual(self.run_cli('examples/unique-tests.xml').returncode, 0)
        self.assertEqual(self.run_cli('examples/retry-collision.xml').returncode, 1)
        self.assertEqual(self.run_cli('missing.xml').returncode, 2)

    def test_json_is_standalone(self):
        result = self.run_cli('examples/retry-collision.xml', '--format', 'json')
        self.assertEqual(result.stderr, '')
        self.assertEqual(json.loads(result.stdout)['summary']['potential_hidden_failure_groups'], 1)

    def test_glob(self):
        result = self.run_cli('examples/shard-*.xml', '--format', 'json')
        self.assertEqual(json.loads(result.stdout)['summary']['parsed_files'], 2)
        self.assertEqual(result.returncode, 1)

    def test_explicit_scope(self):
        self.assertEqual(self.run_cli('examples/shard-*.xml', '--scope', 'file').returncode, 0)

    def test_explicit_identity(self):
        self.assertEqual(self.run_cli('examples/shard-*.xml', '--identity', 'suite-class-name').returncode, 0)

    def test_duplicate_path_arguments_deduplicated(self):
        r = self.run_cli('examples/unique-tests.xml', './examples/unique-tests.xml', '--format', 'json')
        self.assertEqual(json.loads(r.stdout)['summary']['parsed_files'], 1)
        self.assertEqual(r.returncode, 0)

    def test_malformed_xml_no_raw_content(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'bad.xml'
            p.write_text('<SECRET_VALUE>', encoding='utf-8')
            r = self.run_cli(str(p), '--format', 'json')
            self.assertEqual(r.returncode, 2)
            self.assertNotIn('SECRET_VALUE', r.stdout)

    def test_unknown_and_unsupported_encodings_exit_two_without_disclosure(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'encoding.xml'
            for encoding in ["BOGUS_ENCODING_SECRET", "UTF-32", "UTF-7"]:
                with self.subTest(encoding=encoding):
                    p.write_text(f'<?xml version="1.0" encoding="{encoding}"?>' + suite(case()), encoding='utf-8')
                    r = self.run_cli(str(p), '--format', 'json')
                    self.assertEqual(r.returncode, 2)
                    self.assertEqual(r.stderr, '')
                    self.assertEqual(json.loads(r.stdout)['diagnostics'][0]['code'], 'INVALID_XML')
                    self.assertNotIn(encoding, r.stdout)

    def test_missing_glob_json_error(self):
        r = self.run_cli('nonexistent/*.xml', '--format', 'json')
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)['status'], 'invalid')

    def test_inputs_unchanged(self):
        p = ROOT / 'examples/retry-collision.xml'
        before = hashlib.sha256(p.read_bytes()).digest()
        self.run_cli(str(p))
        self.assertEqual(hashlib.sha256(p.read_bytes()).digest(), before)

    def test_directory_rejected(self):
        self.assertEqual(self.run_cli('examples').returncode, 2)

    def test_empty_report(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'empty.xml'
            p.write_text('<testsuite/>', encoding='utf-8')
            self.assertEqual(self.run_cli(str(p)).returncode, 1)

    def test_literal_glob_character_in_filename(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'report[1].xml'
            p.write_text(suite(case()), encoding='utf-8')
            self.assertEqual(self.run_cli(str(p)).returncode, 0)

    def test_output_escapes_untrusted_terminal_characters(self):
        xml = suite(case('x&#10;y') * 2)
        r = inspect_reports([('escape\x1b[31m.xml', io.BytesIO(xml.encode()))])
        text = render_text(r)
        self.assertNotIn('\x1b', text)
        self.assertIn('\\u001b', text)
        self.assertIn('x\\ny', text)

    def test_version(self):
        r = self.run_cli('--version')
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), '0.2.0a1')
        metadata = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        self.assertEqual(r.stdout.strip(), metadata['project']['version'])

    def test_no_reports_usage_error(self):
        self.assertEqual(self.run_cli().returncode, 2)


if __name__ == '__main__':
    unittest.main()
