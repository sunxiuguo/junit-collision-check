"""Streaming XML inspection; never retain report output or failure messages."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import BinaryIO, Iterable
from xml.parsers import expat


@dataclass(frozen=True)
class Limits:
    max_file_bytes: int = 32 * 1024 * 1024
    max_total_bytes: int = 128 * 1024 * 1024
    max_cases: int = 200_000
    max_depth: int = 64
    max_identity_chars: int = 4096
    max_files: int = 1000

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in asdict(self).values()):
            raise ValueError("Limits must be positive integers")


class InputError(ValueError):
    def __init__(self, code: str, message: str, line: int = 0):
        super().__init__(message)
        self.code = code
        self.line = line


@dataclass(frozen=True)
class Case:
    source: str
    line: int
    ordinal: int
    suites: tuple[str, ...]
    classname: str
    name: str
    status: str
    retry_metadata: bool = False

    def location(self):
        return {
            "source": self.source,
            "line": self.line,
            "testcase": self.ordinal,
            "suites": list(self.suites),
            "status": self.status,
            "retry_metadata": self.retry_metadata,
        }


_TERMINAL = {"failure", "error", "skipped"}
_RETRY = {"flakyFailure", "flakyError", "rerunFailure", "rerunError"}
_STRUCTURE = {"testsuites", "testsuite", "testcase"} | _TERMINAL | _RETRY


def _split_name(name):
    return name.rsplit("}", 1) if "}" in name else ("", name)


def parse_report(stream: BinaryIO, source: str, limits: Limits | None = None):
    """Return (cases, byte_count) for one complete supported report.

    Raises InputError and discards the entire file on malformed/unsupported input.
    The caller owns the stream. No files, URLs or external entities are opened.
    """
    limits = limits or Limits()
    if expat.version_info < (2, 6, 0):
        raise InputError("UNSAFE_XML_RUNTIME", "Expat 2.6.0 or newer is required")
    parser = expat.ParserCreate(namespace_separator="}")
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    stack = []
    suites = []
    cases = []
    current = None
    root_namespace = ""
    byte_count = 0

    def fail(code, message):
        raise InputError(code, message, parser.CurrentLineNumber)

    def reject_doctype(*_args):
        fail("FORBIDDEN_DTD", "DTD declarations and custom entities are not supported")

    def reject_external(*_args):
        fail("FORBIDDEN_ENTITY", "External entities are not supported")

    def short(value):
        if len(value) > limits.max_identity_chars:
            fail("IDENTITY_LIMIT", "An identity or suite name exceeds the character limit")
        return value

    def start(expanded, attrs):
        nonlocal current, root_namespace
        namespace, name = _split_name(expanded)
        parent = stack[-1] if stack else None
        if not stack:
            if name not in {"testsuite", "testsuites"}:
                fail("UNSUPPORTED_ROOT", "Expected a testsuite or testsuites root")
            root_namespace = namespace
        if name in _STRUCTURE and namespace != root_namespace:
            fail("MIXED_NAMESPACE", "JUnit elements must use the root namespace consistently")
        if len(stack) >= limits.max_depth:
            fail("DEPTH_LIMIT", "XML nesting exceeds the configured limit")
        if name == "testsuites" and parent is not None:
            fail("UNSUPPORTED_STRUCTURE", "Nested testsuites containers are not supported")
        if name == "testsuite":
            if parent not in {None, "testsuites", "testsuite"}:
                fail("UNSUPPORTED_STRUCTURE", "testsuite must be inside the report or another suite")
            suites.append(short(attrs.get("name", "")))
        elif name == "testcase":
            if parent != "testsuite" or current is not None:
                fail("UNSUPPORTED_STRUCTURE", "testcase must be a direct child of testsuite")
            if len(cases) >= limits.max_cases:
                fail("CASE_LIMIT", "Report exceeds the configured testcase limit")
            name_attr = short(attrs.get("name", ""))
            if not name_attr.strip():
                fail("MISSING_TEST_NAME", "Every testcase needs a nonempty name attribute")
            current = {
                "source": source, "line": parser.CurrentLineNumber,
                "ordinal": len(cases) + 1, "suites": tuple(suites),
                "classname": short(attrs.get("classname", "")), "name": name_attr,
                "results": set(), "retry_metadata": False,
            }
        elif name in _TERMINAL | _RETRY:
            if parent != "testcase" or current is None:
                fail("UNSUPPORTED_STRUCTURE", "Result elements must be direct children of testcase")
            if name in _TERMINAL:
                current["results"].add(name)
            else:
                current["retry_metadata"] = True
        stack.append(name)

    def end(expanded):
        nonlocal current
        _, name = _split_name(expanded)
        if name == "testcase":
            results = current.pop("results")
            if len(results) > 1:
                fail("CONFLICTING_RESULT_ELEMENTS", "A testcase has conflicting terminal result types")
            current["status"] = next(iter(results)) if results else "passed"
            cases.append(Case(**current))
            current = None
        elif name == "testsuite":
            suites.pop()
        stack.pop()

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.EntityDeclHandler = reject_doctype
    parser.ExternalEntityRefHandler = reject_external
    # Text is deliberately ignored: no test output, stack traces or attachments.
    try:
        while True:
            chunk = stream.read(min(65536, limits.max_file_bytes - byte_count + 1))
            if not isinstance(chunk, bytes):
                raise TypeError("parse_report expects a binary stream")
            byte_count += len(chunk)
            if byte_count > limits.max_file_bytes:
                fail("FILE_SIZE_LIMIT", "Report exceeds the configured byte limit")
            parser.Parse(chunk, not chunk)
            if not chunk:
                break
    except InputError:
        raise
    except (expat.ExpatError, LookupError, ValueError) as exc:
        line = getattr(exc, "lineno", parser.CurrentLineNumber)
        raise InputError("INVALID_XML", "XML is malformed or uses an unsupported encoding", line) from None
    return cases, byte_count


def inspect_reports(reports: Iterable[tuple[str, BinaryIO]], *,
                    identity: str = "class-name", scope: str = "all",
                    limits: Limits | None = None):
    """Inspect explicit report streams. All streams belong to one logical run.

    Identity defaults to (classname, name), across all input files. Set scope=file
    only when each file is intentionally a separate result population. The
    alternative suite-class-name identity includes the complete suite lineage.
    Neither mode claims to emulate every CI consumer.
    """
    if identity not in {"class-name", "suite-class-name"}:
        raise ValueError("Unknown identity mode")
    if scope not in {"all", "file"}:
        raise ValueError("Unknown scope")
    limits = limits or Limits()
    groups = defaultdict(list)
    diagnostics = []
    files = []
    total_bytes = 0
    total_cases = 0
    retry_cases = 0
    invalid = False
    seen_sources = set()
    for source, stream in reports:
        if len(files) >= limits.max_files:
            diagnostics.append({"code": "FILE_COUNT_LIMIT", "source": source, "line": 0,
                                "message": "Too many report files"})
            invalid = True
            break
        if source in seen_sources:
            diagnostics.append({"code": "DUPLICATE_SOURCE", "source": source, "line": 0,
                                "message": "The same report source was provided more than once"})
            invalid = True
            continue
        seen_sources.add(source)
        try:
            remaining_bytes = limits.max_total_bytes - total_bytes
            remaining_cases = limits.max_cases - total_cases
            if remaining_bytes < 1 or remaining_cases < 1:
                raise InputError("TOTAL_LIMIT", "Report set reached its byte or testcase limit")
            file_limits = Limits(
                max_file_bytes=min(limits.max_file_bytes, remaining_bytes),
                max_total_bytes=limits.max_total_bytes, max_cases=remaining_cases,
                max_depth=limits.max_depth, max_identity_chars=limits.max_identity_chars,
                max_files=limits.max_files,
            )
            cases, size = parse_report(stream, source, file_limits)
        except InputError as exc:
            invalid = True
            files.append({"source": source, "status": "invalid"})
            diagnostics.append({"code": exc.code, "source": source, "line": exc.line,
                                "message": str(exc)})
            # Stop here: an invalid file must not bypass the aggregate byte limit.
            break
        files.append({"source": source, "status": "parsed", "bytes": size, "cases": len(cases)})
        total_bytes += size
        total_cases += len(cases)
        for case in cases:
            key = ((source if scope == "file" else ""),
                   case.suites if identity == "suite-class-name" else (),
                   case.classname, case.name)
            groups[key].append(case)
            retry_cases += case.retry_metadata

    collisions = []
    for key, cases in sorted(groups.items()):
        if len(cases) < 2:
            continue
        outcomes = sorted({case.status for case in cases})
        has_failure = any(status in {"failure", "error"} for status in outcomes)
        has_nonfailure = any(status in {"passed", "skipped"} for status in outcomes)
        collision = {
            "code": "CONFLICTING_OUTCOMES" if len(outcomes) > 1 else "DUPLICATE_IDENTITY",
            "identity": {"classname": key[2], "name": key[3]},
            "outcomes": outcomes,
            "potential_hidden_failure": has_failure and has_nonfailure,
            "occurrences": [case.location() for case in cases],
        }
        if identity == "suite-class-name":
            collision["identity"]["suites"] = list(key[1])
        if scope == "file":
            collision["identity"]["source"] = key[0]
        collisions.append(collision)
    if not files and not invalid:
        invalid = True
        diagnostics.append({"code": "NO_REPORTS", "source": "", "line": 0,
                            "message": "No report inputs were supplied"})
    if total_cases == 0 and not invalid:
        diagnostics.append({"code": "EMPTY_REPORT_SET", "source": "", "line": 0,
                            "message": "No testcases were found; an empty report is not a clean check"})
    return {
        "schema_version": 1,
        "status": "invalid" if invalid else "issues" if collisions or not total_cases else "clean",
        "identity_mode": identity, "scope": scope,
        "summary": {"parsed_files": sum(f["status"] == "parsed" for f in files),
                    "testcases": total_cases, "unique_identities": len(groups),
                    "duplicate_records": sum(len(c) - 1 for c in groups.values()),
                    "collision_groups": len(collisions),
                    "potential_hidden_failure_groups": sum(c["potential_hidden_failure"] for c in collisions),
                    "cases_with_retry_metadata": retry_cases},
        "files": files, "collisions": collisions, "diagnostics": diagnostics,
    }
