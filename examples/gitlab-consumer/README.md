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
attribute-based identities. Missing/blank suite names, XML namespaces, `type`
attributes, structural text, status attributes on testcase and unknown
elements/attributes return exit 2 with
`UNSUPPORTED_GITLAB_PROFILE`. The consumer itself supports a broader dialect,
including a job-name fallback for missing suite names; this tool does not guess
that job context. Converter ambiguities such as `nil="true"` or `failure="..."`
attributes are rejected rather than interpreted as valid identity records.
Supported attributes are: testsuites: name/time/tests/failures/errors/skipped/disabled;
testsuite: those plus timestamp/hostname/package/id/file/assertions; testcase:
name/classname/file/line/time/assertions; failure/error/skipped: message;
property: name/value. System-out, system-err and properties accept no attributes.
Only these elements are accepted, with whitespace-only text in structural
containers. Result/output/property text is ignored. This deliberately rejects
some valid reports (including result `type` attributes) rather than claiming
full XML-converter parity. All existing safety and input limits still apply.

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

No hosted pipeline, artifact upload, UI, database persistence, cross-job merge,
other GitLab release, or producer runtime was tested. This profile does not audit
consumer timing totals or infer retry order. Recheck against the deployed
consumer version before relying on it; the evidence is version-specific.
