import hashlib
import io
import json
import unittest
import tempfile
from pathlib import Path
from contextlib import redirect_stdout
from junit_collision_check.cli import main
from junit_collision_check.core import inspect_reports, Limits
from junit_collision_check.cli import render_text

def case(cls='a', name='b', attr=None, values=()):
    attribute='' if attr is None else f' custom_automation_id="{attr}"'
    props=''.join(f'<property name="testrail_case_field" value="custom_automation_id:{v}"/>' for v in values)
    return f'<testcase classname="{cls}" name="{name}"{attribute}><properties>{props}</properties></testcase>'

def audit(body, **kw):
    xml='<testsuite name="s">'+body+'</testsuite>'
    return inspect_reports([('synthetic',io.BytesIO(xml.encode()))], identity='testrail', **kw)

class TestRailTests(unittest.TestCase):
    def test_dot_collision_and_default_unchanged(self):
        body=case('a.b','c')+case('a','b.c')
        self.assertEqual(audit(body)['status'],'issues')
        r=inspect_reports([('s',io.BytesIO(('<testsuite>'+body+'</testsuite>').encode()))])
        self.assertEqual(r['status'],'clean')

    def test_precedence_and_last_property(self):
        for attr,values,expected in [('attr',('prop',),'prop'),('attr',('',),'attr'),(None,('',),'a.b'),('attr',('first','last'),'last')]:
            with self.subTest(attr=attr,values=values):
                r=audit(case(attr=attr,values=values)*2)
                self.assertEqual(r['collisions'][0]['identity'],{'consumer_key_sha256':hashlib.sha256(expected.encode()).hexdigest()})

    def test_explicit_ids_override_tuple(self):
        self.assertEqual(audit(case('a','b','same')+case('c','d','same'))['status'],'issues')
        self.assertEqual(audit(case(attr='first')+case(attr='second'))['status'],'clean')

    def test_empty_ids_invalid_and_no_partial_file(self):
        for attr,values in [('',()),('',('',)),('attr',('   ',))]:
            r=audit(case(attr=attr,values=values))
            self.assertEqual(r['status'],'invalid')
            self.assertEqual(r['diagnostics'][0]['code'],'EMPTY_TESTRAIL_ID')
            self.assertEqual(r['summary']['testcases'],0)

    def test_reject_unsupported_shapes(self):
        bodies=['<testcase name="a"/>','<testsuite name="nested">'+case()+'</testsuite>',
                '<properties/>',case(values=('x',)).replace('testrail_case_field','test_id'),
                '<testcase name="b" classname="a"><properties><property name="testrail_case_field" value="custom_case_automation_id:x"/></properties></testcase>',
                case(values=('[1]',)),case(values=('x',)).replace('testrail_case_field','testrail_case_field_1'),
                case(values=('x',)).replace('/></properties>','>secret text</property></properties>'),
                '<testcase name="x" classname="y"><properties><property name="testrail_case_field"/></properties></testcase>',
                '<testcase name="x" classname="y"><flakyFailure/></testcase>']
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(audit(body)['status'],'invalid')

    def test_namespace_and_malformed_rejected(self):
        for xml in ['<testsuite xmlns="urn:x" name="s"/>','<testsuite name="s"><testcase>','<!DOCTYPE testsuite><testsuite name="s"/>']:
            self.assertEqual(inspect_reports([('s',io.BytesIO(xml.encode()))],identity='testrail')['status'],'invalid')

    def test_limits_and_privacy(self):
        self.assertEqual(audit(case(attr='long'),limits=Limits(max_identity_chars=3))['diagnostics'][0]['code'],'IDENTITY_LIMIT')
        body=case(attr='secret-identity')*2
        r=audit(body)
        self.assertNotIn('secret-identity',json.dumps(r)+render_text(r))
        self.assertIn('TestRail key',render_text(r))
        self.assertEqual(audit(body,limits=Limits(max_cases=1))['status'],'invalid')

    def test_scope_and_conflicting_outcome(self):
        xml=('<testsuite name="s">'+case(attr='id')+'</testsuite>').encode()
        r=inspect_reports([('a',io.BytesIO(xml)),('b',io.BytesIO(xml))],identity='testrail',scope='file')
        self.assertEqual(r['status'],'clean')
        r=audit(case(attr='id')+case(attr='id').replace('</testcase>','<failure>private output</failure></testcase>'))
        self.assertTrue(r['collisions'][0]['potential_hidden_failure'])
        self.assertNotIn('private output',json.dumps(r))

    def test_cli_exits_json_and_input_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.xml'
            for body,code in [(case(attr='one')+case(attr='two'),0),(case(attr='same')*2,1),(case(attr=''),2)]:
                data=('<testsuite name="s">'+body+'</testsuite>').encode()
                path.write_bytes(data)
                output=io.StringIO()
                with redirect_stdout(output):
                    result=main([str(path),'--identity','testrail','--format','json'])
                self.assertEqual(result,code)
                self.assertEqual(json.loads(output.getvalue())['identity_mode'],'testrail')
                self.assertEqual(path.read_bytes(),data)
