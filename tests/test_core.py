import io
import json
import unittest
from unittest.mock import patch

from junit_collision_check import InputError, Limits, inspect_reports, parse_report


def report(xml, **kwargs):
    return inspect_reports([("report.xml", io.BytesIO(xml.encode()))], **kwargs)


def case(name="works", cls="Thing", result="", attrs=""):
    return f'<testcase name="{name}" classname="{cls}" {attrs}>{result}</testcase>'


def suite(content, name="suite"):
    return f'<testsuite name="{name}">{content}</testsuite>'


class ParseTests(unittest.TestCase):
    def test_single_suite(self):
        r = report(suite(case()))
        self.assertEqual(r["status"], "clean")
        self.assertEqual(r["summary"]["testcases"], 1)

    def test_multiple_suites(self):
        r = report('<testsuites>' + suite(case("a")) + suite(case("b")) + '</testsuites>')
        self.assertEqual(r["summary"]["unique_identities"], 2)

    def test_nested_suites_track_lineage(self):
        cases, _ = parse_report(io.BytesIO(suite(suite(case(), "inner"), "outer").encode()), "x")
        self.assertEqual(cases[0].suites, ("outer", "inner"))

    def test_namespace(self):
        xml = '<j:testsuite xmlns:j="urn:junit"><j:testcase name="a"/></j:testsuite>'
        self.assertEqual(report(xml)["status"], "clean")

    def test_mixed_namespace_is_inconclusive(self):
        r = report('<testsuite xmlns:x="urn:x"><x:testcase name="a"/></testsuite>')
        self.assertEqual(r["diagnostics"][0]["code"], "MIXED_NAMESPACE")

    def test_utf16(self):
        data = '<?xml version="1.0" encoding="utf-16"?>' + suite(case())
        cases, _ = parse_report(io.BytesIO(data.encode("utf-16")), "x")
        self.assertEqual(len(cases), 1)

    def test_builtin_entities_and_unicode(self):
        r = report(suite(case("A &amp; B") + case("健康")))
        self.assertEqual(r["status"], "clean")

    def test_same_outcome_duplicate(self):
        r = report(suite(case() * 2))
        c = r["collisions"][0]
        self.assertEqual(c["code"], "DUPLICATE_IDENTITY")
        self.assertFalse(c["potential_hidden_failure"])

    def test_retry_pattern_conflict(self):
        r = report(suite(case() * 2 + case(result='<failure>no</failure>')))
        self.assertEqual(r["summary"]["duplicate_records"], 2)
        self.assertEqual(r["collisions"][0]["code"], "CONFLICTING_OUTCOMES")
        self.assertTrue(r["collisions"][0]["potential_hidden_failure"])

    def test_different_classes_do_not_collide(self):
        self.assertEqual(report(suite(case(cls="a") + case(cls="b")))["status"], "clean")

    def test_identity_uses_tuple_not_concatenation(self):
        self.assertEqual(report(suite(case(name="BC", cls="A") + case(name="C", cls="AB")))["status"], "clean")

    def test_names_not_trimmed_or_casefolded(self):
        self.assertEqual(report(suite(case("x") + case("X") + case(" x")))["status"], "clean")

    def test_different_suite_names_collide_by_default(self):
        xml = '<testsuites>' + suite(case(), "a") + suite(case(), "b") + '</testsuites>'
        self.assertEqual(report(xml)["status"], "issues")
        self.assertEqual(report(xml, identity="suite-class-name")["status"], "clean")

    def test_suite_lineage_not_flattened(self):
        xml = '<testsuites>' + suite(suite(case(), "inner"), "a") + suite(suite(case(), "inner"), "b") + '</testsuites>'
        self.assertEqual(report(xml, identity="suite-class-name")["status"], "clean")

    def test_missing_class_is_empty_identity(self):
        r = report('<testsuite><testcase name="x"/><testcase name="x"/></testsuite>')
        self.assertEqual(r["collisions"][0]["identity"]["classname"], "")

    def test_result_types(self):
        for tag in ["failure", "error", "skipped"]:
            with self.subTest(tag=tag):
                cases, _ = parse_report(io.BytesIO(suite(case(result=f'<{tag}/>')).encode()), "x")
                self.assertEqual(cases[0].status, tag)

    def test_multiple_failures_same_type_allowed(self):
        self.assertEqual(report(suite(case(result='<failure/><failure/>')))["status"], "clean")

    def test_conflicting_terminal_types(self):
        r = report(suite(case(result='<failure/><skipped/>')))
        self.assertEqual(r["status"], "invalid")
        self.assertEqual(r["diagnostics"][0]["code"], "CONFLICTING_RESULT_ELEMENTS")

    def test_two_failures_do_not_claim_hidden_failure(self):
        r = report(suite(case(result='<failure/>') + case(result='<error/>')))
        self.assertFalse(r["collisions"][0]["potential_hidden_failure"])

    def test_skipped_and_failure_can_hide_failure(self):
        r = report(suite(case(result='<skipped/>') + case(result='<failure/>')))
        self.assertTrue(r["collisions"][0]["potential_hidden_failure"])

    def test_retry_extensions_counted_without_choosing_attempt(self):
        for tag in ["flakyFailure", "flakyError", "rerunFailure", "rerunError"]:
            with self.subTest(tag=tag):
                r = report(suite(case(result=f'<{tag}/><failure/>')))
                self.assertEqual(r["summary"]["cases_with_retry_metadata"], 1)
                self.assertEqual(r["status"], "clean")

    def test_cdata_comments_outputs_not_testcases(self):
        xml = suite(case() + '<system-out><![CDATA[<testcase name="not-a-test"/>]]></system-out><!-- <testcase/> -->')
        self.assertEqual(report(xml)["summary"]["testcases"], 1)

    def test_report_does_not_disclose_failure_or_output(self):
        xml = suite(case(result='<failure message="SECRET_A">SECRET_B</failure><system-out>SECRET_C</system-out>') * 2)
        serialized = json.dumps(report(xml))
        for text in ["SECRET_A", "SECRET_B", "SECRET_C"]:
            self.assertNotIn(text, serialized)

    def test_line_and_ordinal_preserved(self):
        xml = '<testsuite>\n' + case() + '\n' + case() + '\n</testsuite>'
        occurrences = report(xml)["collisions"][0]["occurrences"]
        self.assertEqual([(o["line"], o["testcase"]) for o in occurrences], [(2, 1), (3, 2)])

    def test_empty_report_not_clean(self):
        r = report('<testsuites/>')
        self.assertEqual(r["status"], "issues")
        self.assertEqual(r["diagnostics"][0]["code"], "EMPTY_REPORT_SET")

    def test_invalid_xml_does_not_keep_partial_cases(self):
        r = report('<testsuite>' + case())
        self.assertEqual(r["status"], "invalid")
        self.assertEqual(r["summary"]["testcases"], 0)

    def test_unknown_and_unsupported_encodings_fail_closed(self):
        for encoding in ["BOGUS_ENCODING_SECRET", "UTF-32", "UTF-7"]:
            with self.subTest(encoding=encoding):
                xml = f'<?xml version="1.0" encoding="{encoding}"?>' + suite(case())
                r = report(xml)
                self.assertEqual(r["status"], "invalid")
                self.assertEqual(r["diagnostics"][0]["code"], "INVALID_XML")
                self.assertNotIn(encoding, json.dumps(r))

    def test_missing_or_blank_test_name(self):
        for attrs in ['', 'name=""', 'name="  "']:
            with self.subTest(attrs=attrs):
                self.assertEqual(report(f'<testsuite><testcase {attrs}/></testsuite>')["status"], "invalid")

    def test_unsupported_structures(self):
        inputs = ['<root/>', '<testcase name="a"/>', '<testsuites><testcase name="a"/></testsuites>',
                  '<testsuite><wrapper><testcase name="a"/></wrapper></testsuite>',
                  '<testsuites><testsuites/></testsuites>', '<testsuite><failure/></testsuite>']
        for xml in inputs:
            with self.subTest(xml=xml):
                self.assertEqual(report(xml)["status"], "invalid")

    def test_dtd_rejected_even_without_entities(self):
        self.assertEqual(report('<!DOCTYPE testsuite>' + suite(case()))["diagnostics"][0]["code"], "FORBIDDEN_DTD")

    def test_external_entity_not_loaded(self):
        xml = '<!DOCTYPE testsuite [<!ENTITY x SYSTEM "file:///etc/passwd">]><testsuite>&x;</testsuite>'
        r = report(xml)
        self.assertEqual(r["diagnostics"][0]["code"], "FORBIDDEN_DTD")
        self.assertNotIn("root:", json.dumps(r))

    def test_entity_amplification_rejected(self):
        xml = '<!DOCTYPE testsuite [<!ENTITY a "abc"><!ENTITY b "&a;&a;&a;">]><testsuite>&b;</testsuite>'
        self.assertEqual(report(xml)["diagnostics"][0]["code"], "FORBIDDEN_DTD")

    def test_utf16_dtd_rejected(self):
        xml = ('<?xml version="1.0" encoding="utf-16"?><!DOCTYPE testsuite>' + suite(case())).encode("utf-16")
        with self.assertRaisesRegex(InputError, "DTD"):
            parse_report(io.BytesIO(xml), "x")

    def test_limits(self):
        examples = [(Limits(max_file_bytes=20), suite(case()), "FILE_SIZE_LIMIT"),
                    (Limits(max_cases=1), suite(case() * 2), "CASE_LIMIT"),
                    (Limits(max_depth=2), suite(case(result='<failure/>')), "DEPTH_LIMIT"),
                    (Limits(max_identity_chars=3), suite(case()), "IDENTITY_LIMIT")]
        for limits, xml, code in examples:
            with self.subTest(code=code):
                self.assertEqual(report(xml, limits=limits)["diagnostics"][0]["code"], code)

    def test_exact_file_limit_allowed(self):
        xml = suite(case())
        self.assertEqual(report(xml, limits=Limits(max_file_bytes=len(xml.encode())))["status"], "clean")

    def test_old_expat_fails_closed(self):
        with patch('junit_collision_check.core.expat.version_info', (2, 5, 0)):
            self.assertEqual(report(suite(case()))["diagnostics"][0]["code"], "UNSAFE_XML_RUNTIME")

    def test_limits_reject_invalid_values(self):
        for value in [0, -1, True, 1.5]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Limits(max_cases=value)


class MultiReportTests(unittest.TestCase):
    def inputs(self):
        return [("a.xml", io.BytesIO(suite(case()).encode())),
                ("b.xml", io.BytesIO(suite(case(result='<failure/>')).encode()))]

    def test_cross_file_collision(self):
        r = inspect_reports(self.inputs())
        self.assertEqual(r["summary"]["collision_groups"], 1)
        self.assertTrue(r["collisions"][0]["potential_hidden_failure"])

    def test_explicit_file_scope(self):
        self.assertEqual(inspect_reports(self.inputs(), scope="file")["status"], "clean")

    def test_file_scope_still_finds_within_file_collision(self):
        self.assertEqual(report(suite(case() * 2), scope="file")["status"], "issues")

    def test_report_order_does_not_select_winner(self):
        a = inspect_reports(self.inputs())
        b = inspect_reports(list(reversed(self.inputs())))
        self.assertEqual(a["summary"], b["summary"])
        self.assertEqual(a["collisions"][0]["potential_hidden_failure"], b["collisions"][0]["potential_hidden_failure"])

    def test_no_inputs(self):
        self.assertEqual(inspect_reports([])["status"], "invalid")

    def test_duplicate_source_invalid(self):
        inputs = self.inputs()
        inputs[1] = ("a.xml", inputs[1][1])
        self.assertEqual(inspect_reports(inputs)["status"], "invalid")

    def test_aggregate_byte_limit(self):
        self.assertEqual(inspect_reports(self.inputs(), limits=Limits(max_total_bytes=70))["status"], "invalid")

    def test_aggregate_case_limit(self):
        self.assertEqual(inspect_reports(self.inputs(), limits=Limits(max_cases=1))["status"], "invalid")

    def test_file_count_limit(self):
        self.assertEqual(inspect_reports(self.inputs(), limits=Limits(max_files=1))["diagnostics"][0]["code"], "FILE_COUNT_LIMIT")

    def test_invalid_file_stops_processing(self):
        def inputs():
            yield "invalid.xml", io.BytesIO(b'<broken/>')
            self.fail("Should not read another input after invalid report")
        self.assertEqual(inspect_reports(inputs())["status"], "invalid")

    def test_bad_options(self):
        for kwargs in [{"identity": "unknown"}, {"scope": "unknown"}]:
            with self.assertRaises(ValueError):
                inspect_reports([], **kwargs)


if __name__ == '__main__':
    unittest.main()
