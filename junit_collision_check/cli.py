"""Local-files-only command line interface."""

import argparse
from contextlib import closing
import glob
import json
from pathlib import Path
import stat
import sys

from . import __version__
from .core import Limits, inspect_reports


def _quoted(value):
    # Escape control characters, bidi controls, and terminal escapes from inputs.
    return json.dumps(value, ensure_ascii=True)


def render_text(report):
    s = report["summary"]
    lines = [f"{report['status'].upper()}: {s['testcases']} records, "
             f"{s['unique_identities']} identities, {s['collision_groups']} collision groups",
             f"Identity: {report['identity_mode']}; scope: {report['scope']}"]
    for collision in report["collisions"]:
        identity = collision["identity"]
        if report["identity_mode"] == "gitlab":
            lines.append(f"{collision['code']}: GitLab key {_quoted(identity['consumer_key_sha256'])} / {_quoted(identity['outcome'])}")
        else:
            lines.append(f"{collision['code']}: {_quoted(identity['classname'])} / {_quoted(identity['name'])}")
        if collision["potential_hidden_failure"]:
            lines.append("  A consumer keeping one duplicate could hide a reported failure")
        for item in collision["occurrences"]:
            lines.append(f"  {_quoted(item['source'])}:{item['line']} testcase #{item['testcase']} "
                         f"[{item['status']}] suite={_quoted(item['suites'])}")
    for item in report["diagnostics"]:
        lines.append(f"{item['code']}: {_quoted(item['source'])}:{item['line']} {item['message']}")
    if s["cases_with_retry_metadata"]:
        lines.append(f"Note: {s['cases_with_retry_metadata']} records contain retry metadata; no attempts were selected")
    if report["status"] == "clean":
        lines.append("No identity collisions found; this does not prove tests passed or the run is complete")
    return "\n".join(lines)


def _paths(patterns, max_files):
    result = []
    seen = set()
    for pattern in patterns:
        # Prefer an existing literal path, including names containing glob characters.
        literal = Path(pattern)
        matches = [str(literal)] if literal.is_file() else glob.iglob(pattern, recursive=True)
        found = False
        for match in matches:
            found = True
            path = Path(match)
            if not stat.S_ISREG(path.stat().st_mode):
                raise ValueError(f"Input is not a regular file: {_quoted(match)}")
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            result.append(path)
            if len(result) > max_files:
                raise ValueError(f"At most {max_files} report files are supported")
        if not found:
            raise ValueError(f"No reports matched {_quoted(pattern)}")
    return sorted(result, key=str)


def _streams(paths):
    for path in paths:
        with path.open("rb") as stream:
            yield str(path), stream


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Find JUnit identity collisions across local XML reports without changing them.")
    parser.add_argument("reports", nargs="+", help="Report paths or quoted glob patterns (no URLs)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--identity", choices=["class-name", "suite-class-name", "gitlab"], default="class-name")
    parser.add_argument("--scope", choices=["all", "file"], default="all",
                        help="Use file only if every input is a separate result population")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    limits = Limits()
    try:
        paths = _paths(args.reports, limits.max_files)
        with closing(_streams(paths)) as streams:
            report = inspect_reports(streams, identity=args.identity, scope=args.scope, limits=limits)
    except (OSError, ValueError) as exc:
        # Do not echo XML or file contents. Exceptions here only involve input paths.
        error = {"schema_version": 1, "status": "invalid", "diagnostics": [
            {"code": "INPUT_ERROR", "message": str(exc)}]}
        print(json.dumps(error, ensure_ascii=True, indent=2) if args.format == "json"
              else "INPUT_ERROR: " + _quoted(str(exc)))
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2) if args.format == "json" else render_text(report))
    return {"clean": 0, "issues": 1, "invalid": 2}[report["status"]]
