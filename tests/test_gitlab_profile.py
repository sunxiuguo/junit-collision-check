import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from junit_collision_check import inspect_reports

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples/gitlab-consumer'


class GitlabProfileTests(unittest.TestCase):
    def inspect(self, xml, **kwargs):
        return inspect_reports([('synthetic.xml', io.BytesIO(xml.encode()))], identity='gitlab', **kwargs)

    def test_fixture_cli_matrix(self):
        for name, default_exit, profile_exit in [
            ('duplicate-failures', 1, 1), ('mixed-outcomes', 1, 0),
            ('concatenated-key', 0, 1), ('unique-control', 0, 0),
        ]:
            path = EXAMPLES / (name + '.xml')
            original = path.read_bytes()
            for identity, expected in [('class-name', default_exit), ('gitlab', profile_exit)]:
                with self.subTest(name=name, identity=identity):
                    result = subprocess.run([sys.executable, '-m', 'junit_collision_check',
                        str(path), '--identity', identity, '--format', 'json'], cwd=ROOT,
                        text=True, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    report = json.loads(result.stdout)
                    self.assertNotIn('synthetic first', result.stdout)
                    if identity == 'gitlab':
                        self.assertEqual(report['summary']['potential_hidden_failure_groups'], 0)
                        self.assertEqual(report['summary']['unique_identities'], 1 if expected else 2)
            self.assertEqual(original, path.read_bytes())

    def test_key_matches_pinned_consumer(self):
        report = self.inspect('<testsuite name="synthetic"><testcase classname="A_B" name="C"/><testcase classname="A" name="B_C"/></testsuite>')
        identity = report['collisions'][0]['identity']
        self.assertEqual(identity, {'consumer_key_sha256': hashlib.sha256(b'synthetic_A_B_C').hexdigest(), 'outcome': 'passed'})

    def test_separate_outcome_buckets(self):
        xml = '<testsuite name="s">' + ''.join('<testcase name="a">' + tag + '</testcase>' for tag in ['', '<failure/>', '<error/>', '<skipped/>']) + '</testsuite>'
        self.assertEqual(self.inspect(xml)['summary']['unique_identities'], 4)
        self.assertEqual(self.inspect(xml)['status'], 'clean')

    def test_only_immediate_suite_name_is_used(self):
        xml = '<testsuites>' + ''.join(f'<testsuite name="{parent}"><testsuite name="leaf"><testcase name="x"/></testsuite></testsuite>' for parent in ['one', 'two']) + '</testsuites>'
        self.assertEqual(self.inspect(xml)['summary']['duplicate_records'], 1)

    def test_different_leaf_suites_are_distinct(self):
        xml = '<testsuites>' + ''.join(f'<testsuite name="{name}"><testcase name="x"/></testsuite>' for name in ['one', 'two']) + '</testsuites>'
        self.assertEqual(self.inspect(xml)['status'], 'clean')

    def test_missing_classname_matches_empty_classname(self):
        self.assertEqual(self.inspect('<testsuite name="s"><testcase name="x"/><testcase classname="" name="x"/></testsuite>')['summary']['duplicate_records'], 1)

    def test_unsupported_profiles_fail_explicitly(self):
        for xml in ['<testsuite><testcase name="x"/></testsuite>',
                    '<testsuite name=""><testcase name="x"/></testsuite>',
                    '<testsuite xmlns="urn:test" name="s"><testcase name="x"/></testsuite>',
                    '<testsuite name="s"><testcase name="x" type="array"/></testsuite>',
                    '<testsuite name="s"><testcase name="x"><classname>y</classname></testcase></testsuite>']:
            with self.subTest(xml=xml):
                r = self.inspect(xml)
                self.assertEqual(r['status'], 'invalid')
                self.assertEqual(r['diagnostics'][0]['code'], 'UNSUPPORTED_GITLAB_PROFILE')

    def test_converter_ambiguities_fail_closed(self):
        for xml in [
            '<testsuite name="s"><testcase name="x" failure="oops"/><testcase name="x"><failure/></testcase></testsuite>',
            '<testsuite name="s" nil="true"><testcase name="x"/></testsuite>',
            '<testsuite name="s">payload<testcase name="x"/></testsuite>',
            '<testsuite name="s" __content__="payload"><testcase name="x"/></testsuite>',
            '<testsuite name="s"><testcase name="x" error="oops"/></testsuite>',
            '<testsuite name="s"><testcase name="x" skipped="oops"/></testsuite>',
            '<testsuite name="s"><testcase name="x">payload</testcase></testsuite>',
            '<testsuite name="s"><testcase name="x" _-content-_="payload"/></testsuite>',
        ]:
            with self.subTest(xml=xml):
                report = self.inspect(xml)
                self.assertEqual(report['status'], 'invalid')
                self.assertIn(report['diagnostics'][0]['code'], ['UNSUPPORTED_GITLAB_PROFILE', 'INVALID_XML'])

    def test_file_scope_is_explicit(self):
        data = b'<testsuite name="s"><testcase name="x"/></testsuite>'
        for scope, count in [('all', 1), ('file', 2)]:
            r = inspect_reports([(n, io.BytesIO(data)) for n in ['a', 'b']], identity='gitlab', scope=scope)
            self.assertEqual(r['summary']['unique_identities'], count)

    def test_text_rendering(self):
        p = subprocess.run([sys.executable, '-m', 'junit_collision_check', str(EXAMPLES / 'concatenated-key.xml'), '--identity', 'gitlab'], cwd=ROOT, text=True, capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 1)
        self.assertIn('DUPLICATE_IDENTITY: GitLab key', p.stdout)
