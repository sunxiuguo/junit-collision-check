# Pinned GitLab consumer profile

`--identity gitlab` checks the deduplication key used by the GitLab CE source at
[`5d5ef5930034a1ddd59a94b74f99bd8178150275`](https://github.com/gitlabhq/gitlabhq/commit/5d5ef5930034a1ddd59a94b74f99bd8178150275).
It is opt-in; the existing tuple-based modes are unchanged. This is a source-level
consumer profile, not a hosted GitLab compatibility or adoption claim.

```sh
python -m junit_collision_check examples/gitlab-consumer/concatenated-key.xml --identity gitlab
```

This exits 1. In the pinned consumer, SHA-256 is applied to
`immediate_suite_name + "_" + classname + "_" + name`, and records are stored in
separate status buckets. File/line metadata and ancestor suite names are not key
components. The auditor uses the same joined UTF-8 key and separate outcome
buckets. Missing classname is treated as empty, as in Ruby interpolation.

The mode requires explicit nonblank suite names, unnamespaced XML and untyped,
attribute-based identities. Missing/blank suite names, XML namespaces, structural
text, status attributes on testcase and unknown
elements/attributes return exit 2 with
`UNSUPPORTED_GITLAB_PROFILE`. The consumer itself supports a broader dialect,
including a job-name fallback for missing suite names; this tool does not guess
that job context. Converter ambiguities such as `nil="true"` or `failure="..."`
attributes are rejected rather than interpreted as valid identity records.
Supported attributes are: testsuites: name/time/tests/failures/errors/skipped/disabled;
testsuite: those plus timestamp/hostname/package/id/file/assertions; testcase:
name/classname/file/line/time/assertions/testId/runId; failure: message/type, with
`type` absent or exactly `failed`; error/skipped: message;
property: name/value. System-out, system-err and properties accept no attributes.
Only these elements are accepted, with whitespace-only text in structural
containers. Result/output/property text is ignored. This deliberately rejects
some valid reports rather than claiming full XML-converter parity. Every other
`type` value or placement remains unsupported, including on error/skipped.
All existing safety and input limits still apply.

Audit one job's complete report population with the default `--scope all`.
Run separate audits for different jobs. `--scope file` only models separate
populations when each file genuinely belongs to a different one; using it for
multiple artifacts from the same job hides cross-file collisions.

## Observed controls

All four files are synthetic UTF-8 XML. Each has two testcase records and at least one
failure. The table reports local execution of the unmodified official parser,
XML converter and report classes, not a reimplementation of their behavior.

| Fixture | Default tuple audit | GitLab profile | Pinned parser retained |
| --- | --- | --- | --- |
| duplicate-failures.xml | exit 1 | exit 1 | 1 failed record; later file metadata wins |
| mixed-outcomes.xml | exit 1 | exit 0 | Both records; report remains failed |
| concatenated-key.xml | exit 0 | exit 1 | 1 failed record despite distinct tuples |
| unique-control.xml | exit 0 | exit 0 | Both failed records |

Each case was also run with reversed record order and split across two files
parsed into the same job report: 12 consumer comparisons in total. Profile
unique-identity counts matched retained consumer counts in all 12. Inputs stayed
unchanged. Mixed pass/fail identities remain separate in this consumer, so a
potential-hidden-failure flag in the generic mode is not proof of hidden failure
here. A clean identity audit never means the tests passed or the run is complete.

The GitLab JSON collision identity is `{consumer_key_sha256, outcome}` rather
than `{classname, name}`. Existing modes keep their output shapes. `outcome`
uses the auditor's existing `passed`, `failure`, `error`, `skipped` vocabulary;
it corresponds to separate consumer buckets. Original suite lineage and status
remain in occurrence locations. No XML body/failure message is emitted.

## Verification boundary

Verified on 2026-10-08 with Ruby 3.3.8, ActiveSupport 7.2.3.1 and Nokogiri 1.19.4.
The last two versions and gem checksums match the pinned GitLab Gemfile.lock.
Six upstream runtime files were byte-checked against their Git blob identities:
Junit, ParserError, XmlConverter, TestCase, TestSuite and TestReport. The harness
only supplies a synthetic job name/limit and collects parsed results. End users
do not need Ruby, GitLab, gems, accounts or network access.

Sources: [parser](https://github.com/gitlabhq/gitlabhq/blob/5d5ef5930034a1ddd59a94b74f99bd8178150275/lib/gitlab/ci/parsers/test/junit.rb),
[key](https://github.com/gitlabhq/gitlabhq/blob/5d5ef5930034a1ddd59a94b74f99bd8178150275/lib/gitlab/ci/reports/test_case.rb),
[buckets](https://github.com/gitlabhq/gitlabhq/blob/5d5ef5930034a1ddd59a94b74f99bd8178150275/lib/gitlab/ci/reports/test_suite.rb).

The original four-fixture check did not exercise a hosted pipeline, artifact
upload, UI, database persistence, cross-job merge, other GitLab release or producer
runtime. This profile does not audit
consumer timing totals or infer retry order. Recheck against the deployed
consumer version before relying on it; the evidence is version-specific.

## Bounded TestSprite renderer check

The [reported integration problem](https://github.com/TestSprite/testsprite-cli/issues/515)
is two distinct logical tests with the same readable title in a multi-project
test list. Their `testId`/`runId` metadata does not distinguish the pinned GitLab
key. The existing [upstream fix PR #521](https://github.com/TestSprite/testsprite-cli/pull/521)
changes colliding names. This example credits that work; it does not replace it.

`testsprite-before.xml` and `testsprite-pr521.xml` were generated from synthetic
inputs by the unchanged `buildJUnitReport` renderer at
[`988c0355`](https://github.com/TestSprite/testsprite-cli/blob/988c0355bb05631e9c6c1785e443937ff2a88c0e/src/lib/junit-report.ts)
and [PR head `ade73bf5`](https://github.com/luckyzd/testsprite-cli/blob/ade73bf5b48424d0f987ca635633d7ab95450ffb/src/lib/junit-report.ts).
Both contain two failed cases; the second includes the upstream name suffixes.

```sh
python -m junit_collision_check examples/gitlab-consumer/testsprite-before.xml --identity gitlab
# Audit exit 1; pinned collector retains one failed record and the later diagnostic.
python -m junit_collision_check examples/gitlab-consumer/testsprite-pr521.xml --identity gitlab
# Audit exit 0; pinned collector retains both failed records and both diagnostics.
```

Verified on 2026-10-27 using Node 24.19.0, Ruby 3.3.8, ActiveSupport 7.2.3.1 and
Nokogiri 1.19.4. The actual unchanged GitLab XML converter, parser and four report/
parser support classes were executed, with only a synthetic job name/limit stub.
The renderer's runtime import graph was unchanged; Node's built-in TypeScript
transformation supplied execution without npm dependencies. This executed the
renderer function, not the complete CLI, project lookup, dispatch or polling.
This was not a full GitLab `Gemfile.lock` reproduction: the runtime used default
bigdecimal 3.1.5 and racc 1.7.3, which differed from the pinned lock.

The new profile allowance is only testcase `testId`/`runId` metadata and literal
`failure type="failed"`. Converter checks included nonempty, empty and whitespace
content. Duplicate failures, unique identities, mixed outcomes, passed/skipped
cases and joined-key ambiguity matched retained consumer keys/statuses, including
reversed records and split files. Input bytes stayed unchanged. Metadata is not
printed, but IDs that a producer includes in testcase names remain visible.

Do not generalize this to all TestSprite outcomes or all result `type` values.
The pinned ActiveSupport converter turns `type="integer"` diagnostic content
into a number and can abort parsing for `type="date"`; `symbol`/`yaml` are
disallowed. Reserved types, other unknown values, and error `type` attributes
still return exit 2 with `UNSUPPORTED_GITLAB_PROFILE`, even when a particular
fixture happens to collect successfully. Empty error elements with `type`
attributes were checked but remain unsupported; untyped error elements are still
allowed. The profile audits identity retention, not diagnostic text
or timing parity. There was no hosted GitLab ingestion, UI screenshot, external
adoption, account, credential or service traffic. A clean audit still leaves
both tests failed in the after fixture.
