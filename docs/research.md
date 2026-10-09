# Problem and alternatives

Initial research checked 2026-10-05; retry-plugin evidence refreshed 2026-10-09.
This is a narrow engineering hypothesis, not proven adoption.

## Evidence

[ProgramBench #64](https://github.com/facebookresearch/ProgramBench/issues/64),
opened 2026-09-04, reports that pytest-rerunfailures 16.6.1 can emit several records
for one logical test, including apparent passes before the final failure. The
consumer counted the records separately. The basic demonstration models the
artifact shape synthetically; the optional [installed-plugin experiment](../examples/pytest-rerunfailures/)
now verifies actual reports from versions 16.4, 16.6, 16.6.1 and 16.7. ProgramBench
already pins new evaluator runs to 16.4, so an open issue does not imply its
current default remains exposed. The linked fix PR belongs upstream; this tool
claims neither authorship nor production impact. See the example for the exact
component-test scope and neighboring controls.

[Kubescape #3007](https://github.com/kubescape/kubescape/issues/3007), opened
2026-08-11 and completed 2026-08-14, reports duplicate display names in JUnit
output. It illustrates a distinct producer cause: different checks with identical
identities. It is a resolved historical case, not a reason to avoid current Kubescape.

[GitLab's unit-test-report documentation](https://docs.gitlab.com/ci/testing/unit_test_reports/)
explains missing results caused by duplicate identities. Its current behavior is
evidence for a pre-ingestion check; we do not promise exact compatibility with all
GitLab versions or with other reporters.

## Alternatives already considered

- [junitparser](https://github.com/weiwei/junitparser): mature parsing, editing and
  merging. Its documentation explicitly leaves duplicate handling to the caller.
  Use it when you need to create or transform reports
- [junit-report-doctor-kit](https://github.com/Recoveredd/junit-report-doctor-kit):
  TypeScript normalization, structure diagnostics and counter checks. Its inspected
  documented diagnostics do not include cross-file testcase-identity collisions
- Native CI report UIs and test-history services provide richer presentation and
  trends. This tool runs before upload, offline, with no account or stored history

The differentiator is a report-set identity audit that exposes every colliding
record and conflicting outcome without silently choosing a winner. This is not a
claim that no competing tool exists. If another established tool serves your need,
use that instead.

## Intentional boundaries

No automatic repair: repeated records can mean retries, overlapping shards,
parameter-name bugs, or intentionally separate matrix populations. Selecting
first/last/worst without that context can change the truth. No runner execution,
expected-test inventory, flaky-test scoring, historical database or arbitrary plugin
loading is part of v0.1.

All implementation and fixtures in this repository are original. Public issues
informed failure classes; upstream code and XML fixtures were not copied.
