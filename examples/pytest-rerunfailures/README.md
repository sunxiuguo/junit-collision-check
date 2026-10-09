# Check actual retry-plugin output before scoring

This optional experiment runs **pytest 9.1.1** with installed official
`pytest-rerunfailures` releases and original synthetic tests. Unlike the
hand-authored retry XML in the basic demo, these records are emitted by the real
plugin. It audits them without rewriting the reports or selecting a retry winner.

## Run

Use a fresh virtual environment and Python 3.12+ with Expat 2.6.0+. From the
repository root, install one pinned combination, then run the example:

```sh
python -m pip install 'pytest==9.1.1' 'pytest-rerunfailures==16.7'
python examples/pytest-rerunfailures/demo.py --plugin-version 16.7
```

Repeat in separate virtual environments with plugin **16.4**, **16.6**, and
**16.6.1**, passing the matching `--plugin-version`. The script refuses a version
mismatch. Installation requires package-index access; the script has no network
step. These packages are example-only dependencies, not auditor dependencies.
It disables third-party plugin autoload, uses a private temporary configuration,
runs only fixed synthetic tests, and removes its generated reports afterward.

## Observed results

Verified on Linux / Python 3.12.14 / Expat 2.8.3 with the unmodified auditor at
[`56f68a8`](https://github.com/sunxiuguo/junit-collision-check/commit/56f68a8235a8caae89c102e9c9774e345c624099).

| Synthetic test | Plugin | pytest exit | XML records | Audit exit |
| --- | --- | --- | --- | --- |
| Fails after two reruns | 16.4 / 16.6 | 1 | 1 failure | 0 |
| Fails after two reruns | 16.6.1 / 16.7 | 1 | 2 empty + 1 failure | 1 |
| Passes on third attempt | 16.4 / 16.6 | 0 | 1 pass | 0 |
| Passes on third attempt | 16.6.1 / 16.7 | 0 | 3 empty records | 1 |
| Passes immediately | All four | 0 | 1 pass | 0 |
| Fails, no reruns | All four | 1 | 1 failure | 0 |

Each version runs four scenarios. The failed-retry collision is
`CONFLICTING_OUTCOMES` with a potential-hidden-failure flag. The eventual-pass
collision is only `DUPLICATE_IDENTITY`; it does not claim a hidden failure.
The verifier checks record counts, runner and audit exits, collision diagnostics,
failure preservation and unchanged XML bytes.

**An audit exit of 0 never means the tests passed.** Keep the test runner's exit
status as an independent required gate. The example itself succeeds only when
all expected outcomes, including intentional test failures, are observed.

## Consumer evidence and existing mitigation

[ProgramBench #64](https://github.com/facebookresearch/ProgramBench/issues/64)
reported this class of scoring error. Its proposed
[PR #63](https://github.com/facebookresearch/ProgramBench/pull/63) was still open
when checked on 2026-10-09, but that alone does **not** establish an exposed
current default workflow. ProgramBench already
[pinned the evaluator to 16.4 on September 8](https://github.com/facebookresearch/ProgramBench/commit/b08d8621031f5f5abc4d3ffc2950256c83fbfe42).
The 16.4 control above emits one final result, avoiding this producer shape.

A separate local component experiment supplied the generated XML to unchanged
`TestResult`, `TestBranchError`, `EvaluationResult` and `parse_test_results`
definitions selected from
[ProgramBench main `27f02157`](https://github.com/facebookresearch/ProgramBench/blob/27f02157c785f8da3647aa6dbbe6b9137f99f10e/src/programbench/eval/eval.py).
With junitparser 4.0.2 and Pydantic 2.12.5, the 16.6.1/16.7 always-failing reports
became two passes plus one failure, score 2/3. The 16.4/16.6 reports scored 0.
This was an isolated parser/model-component test using exact AST definitions;
it did not run ProgramBench's installation, Docker evaluator, datasets, model,
network controls or production workflow. Error exception classes were placeholders
on unexercised invalid-input paths. The self-contained example here reproduces
the producer/auditor portion, not that consumer harness.

The [plugin changelog](https://github.com/pytest-dev/pytest-rerunfailures/blob/master/CHANGES.rst)
records changed teardown reporting in 16.6.1. This experiment does not assert a
new upstream bug or prescribe downgrading: use your producer's supported fix or
configuration and your consumer's intended retry semantics.

[junitparser](https://github.com/weiwei/junitparser#merge-xml-files) explicitly
leaves duplicate handling to callers when merging. ProgramBench's existing pin
addresses new report generation; its proposed PR addresses interpretation of
already duplicated reports. This auditor supplies a separate fail-fast artifact
check and deliberately does not choose first, last or worst result.

No hosted GitLab ingestion, cross-platform execution, general plugin
compatibility, external adoption or production impact was verified. No release,
version or auditor runtime changes are needed for this example.
