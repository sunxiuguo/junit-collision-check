# Contract v1

## Identity

An identity is a tuple, not a concatenated string, to avoid `A + BC == AB + C`
collisions. The default tuple is `(classname, name)`. Optional suite identity is
`(tuple(suite_names_from_root), classname, name)`. File scope prefixes either tuple
with the caller's report source. Exact decoded XML attribute values are used.

Every testcase must have a nonblank name and be directly inside a testsuite.
Unknown metadata is ignored, but JUnit structural/result elements in unsupported
locations are rejected. Suite `tests`/`failures` counters are not trusted or audited.
Nested `testsuites` wrappers are unsupported. Consistently namespaced documents are
accepted; mixing namespaces for known structural/result elements is rejected.

## Opt-in GitLab profile

`identity="gitlab"` models the pinned source key and status buckets described in
[the consumer evidence](../examples/gitlab-consumer/). It requires named suites
and a narrower XML subset; unsupported profile inputs fail explicitly. Its
collision identity contains `consumer_key_sha256` and `outcome`; tuple modes
retain their existing fields. Default identity and scope are unchanged.

## Stable codes

Collision codes:
- `DUPLICATE_IDENTITY`: at least two records share the identity with one status
- `CONFLICTING_OUTCOMES`: at least two records share the identity with different statuses

Input diagnostic codes:
- `INPUT_ERROR`: CLI file selection/opening problem
- `NO_REPORTS`, `EMPTY_REPORT_SET`, `DUPLICATE_SOURCE`
- `INVALID_XML`, `UNSUPPORTED_ROOT`, `UNSUPPORTED_STRUCTURE`, `MIXED_NAMESPACE`
- `MISSING_TEST_NAME`, `CONFLICTING_RESULT_ELEMENTS`
- `UNSUPPORTED_GITLAB_PROFILE`
- `FORBIDDEN_DTD`, `FORBIDDEN_ENTITY`, `UNSAFE_XML_RUNTIME`
- `FILE_SIZE_LIMIT`, `FILE_COUNT_LIMIT`, `CASE_LIMIT`, `TOTAL_LIMIT`, `DEPTH_LIMIT`, `IDENTITY_LIMIT`

The aggregate byte allowance is enforced by reducing the next file's byte limit;
exceeding it may therefore be reported as `FILE_SIZE_LIMIT`. Counts include only
fully parsed files. Input processing stops on a failed file. Invalid input always
wins over earlier collision findings for the overall exit status.

## Output

The JSON result contains `schema_version`, `status`, `identity_mode`, `scope`,
`summary`, `files`, `collisions` and `diagnostics`. A CLI selection/open error may
contain only `schema_version`, `status` and `diagnostics` because no reliable audit
was produced. Argument syntax errors use argparse's stderr and exit 2.

A collision includes identity components, outcome names, potential-hidden-failure
flag, and ordered occurrences. Each occurrence has source, 1-based line, 1-based
record ordinal in that file, suite lineage, reported status and retry-metadata flag.
Groups are sorted by identity. Occurrences preserve input order; this order is not
an execution timeline. CLI file enumeration is sorted, API input order is preserved.

Output never includes XML body text or failure-message attributes. Test and suite
names are not secret-redacted. Text output JSON-escapes input-derived strings so
control characters cannot become terminal control sequences.
