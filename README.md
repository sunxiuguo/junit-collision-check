# junit-collision-check

**Find the test failures that duplicate JUnit identities can hide.**

A small, offline Python CLI for teams combining JUnit XML from shards, retries,
and matrix jobs. It groups records by test identity, points to every occurrence,
and highlights conflicting outcomes before a report consumer discards a duplicate.

- Cross-file and within-file collisions, with file, line, suite and record number
- Explicit identity and scope controls for matrix runs
- Text or JSON; CI-friendly exit codes
- No runtime dependencies, accounts, network access, telemetry or report rewriting

## Try the failure in 30 seconds

Requires Python 3.12+ with Expat 2.6.0+. Use a current, patched Python release.
The first hosted validation found older Expat builds in Windows/macOS Python 3.10;
initial supported versions start at 3.12 rather than bypassing the XML safety check.
From this source checkout, no installation is needed:

```sh
python -m junit_collision_check examples/retry-collision.xml
```

```text
ISSUES: 3 records, 1 identities, 1 collision groups
Identity: class-name; scope: all
CONFLICTING_OUTCOMES: "cart.CheckoutTest" / "rejects_expired_coupon"
  A consumer keeping one duplicate could hide a reported failure
  "examples/retry-collision.xml":3 testcase #1 [passed] suite=["checkout"]
  "examples/retry-collision.xml":4 testcase #2 [passed] suite=["checkout"]
  "examples/retry-collision.xml":5 testcase #3 [failure] suite=["checkout"]
```

The command intentionally exits **1**. Three records describe one test, with
incompatible outcomes. It does not select a winner or assume file order is retry order.

Now try the distinct-test control:

```sh
python -m junit_collision_check examples/unique-tests.xml
python scripts/demo.py
```

The control exits 0. The demo verifies both results and exits 0 if they match.
All fixtures are synthetic. No test runner or external service is started.

## Use it on a report set

```sh
python -m junit_collision_check 'reports/**/*.xml'
python -m junit_collision_check 'reports/**/*.xml' --format json > collision-report.json
```

Quote globs so the CLI expands them consistently. Missing matches, unreadable files,
malformed XML and unsupported structures fail with exit 2. Repeated references to
the same resolved path are included once. Only regular local files are accepted.

To install from a reviewed local checkout into your virtual environment:

```sh
python -m pip install .
junit-collision-check 'reports/**/*.xml'
```

No PyPI publication is assumed by these instructions. The build uses setuptools;
the installed CLI itself has no dependencies beyond Python's standard library.

### Choose the right identity

For the pinned GitLab source consumer, see the opt-in
[`--identity gitlab` profile and observed controls](examples/gitlab-consumer/).
It models joined-string key collisions and separate status buckets; it does not
claim hosted compatibility. Existing default tuple semantics are unchanged.

The default is the exact pair `(classname, name)` across all inputs. Suite labels
and filenames do not distinguish tests in this mode. A missing classname is `""`.
Case, whitespace and Unicode are preserved, not normalized.

For a consumer that uses the full suite lineage as part of identity:

```sh
python -m junit_collision_check 'reports/**/*.xml' --identity suite-class-name
```

For independent matrix populations, inspect each population separately. If each
file is deliberately independent, use:

```sh
python -m junit_collision_check 'reports/**/*.xml' --scope file
```

`--scope file` cannot find cross-file collisions. Do not use it to hide overlapping
shards that your downstream tool merges. Likewise, only add suite names to identity
when your actual consumer does. Different consumers and versions group tests
differently; this tool is an explicit identity audit, not a complete CI emulator.

## What a result means

| Exit | Meaning |
| --- | --- |
| 0 | Nonempty parsed report set; no collisions under the selected identity/scope |
| 1 | Duplicate identities, conflicting outcomes, or an empty report set |
| 2 | Invalid input, unsupported XML structure, or a resource/runtime limit |

**Exit 0 does not mean tests passed.** A report with one unique failed test has no
identity collision. Keep your test runner's exit status and normal test-result gate.
The tool also cannot prove that all expected tests ran, or that the supplied files
belong to the same run. Supply one intentional result population per invocation.

A `potential_hidden_failure` means a collision group contains both a failure/error
and a passed/skipped record. A consumer retaining a nonfailing occurrence could
conceal the failure. This is a risk signal, not a claim about which record your CI
actually retained. Even same-outcome duplicates exit 1 because they can inflate counts.

The parser uses direct `<failure>`, `<error>` and `<skipped>` children for status;
no such child means *reported passed*. Repeated results of the same type are accepted;
conflicting terminal types make the file invalid. Maven-style retry elements are
counted as metadata, never collapsed or selected as the final attempt.

## CI integration

After your runner has written all reports, run the CLI as a separate required check.
Preserve its exit status; do not append `|| true`. Run it even if the test command
failed, using your CI system's normal “always run” mechanism. Keep report artifacts
and test-runner failures independently visible.

For a source checkout already present in a tools directory:

```sh
python tools/junit-collision-check/scripts/check_reports.py 'test-results/**/*.xml'
```

This helper finds the package beside itself without requiring a global install.
Pin the tools checkout to a reviewed commit. There is no automatic code downloader.

For a runnable example with **real pytest-generated reports**, see
[Keep test failures and identity collisions as separate gates](examples/pytest-ci/).
It verifies disjoint shards, overlapping shards, unique failures and conflicting
attempts. It includes [GitHub Actions](examples/pytest-ci/#minimal-github-actions-recipe)
and [GitLab CI](examples/pytest-ci/#minimal-gitlab-ci-recipe) recipes that preserve
test failures while checking report identities.

## Python API

```python
from junit_collision_check import inspect_reports

with open("shard-a.xml", "rb") as a, open("shard-b.xml", "rb") as b:
    result = inspect_reports([("shard-a.xml", a), ("shard-b.xml", b)])

assert result["status"] == "clean", result["collisions"]
```

Streams are owned by the caller. Invalid reports produce `status: "invalid"`;
parsing stops at the first invalid file. Any earlier counts are partial, never a
successful audit. JSON uses `schema_version: 1` and stable diagnostic codes.
See [input and output contract](docs/contract.md).

## Why this exists

- [ProgramBench #64](https://github.com/facebookresearch/ProgramBench/issues/64)
  describes retry records causing a failed test to contribute passing records to
  a score. It was open when checked on 2026-10-05, with an upstream fix proposed
  in [#63](https://github.com/facebookresearch/ProgramBench/pull/63)
- [Kubescape #3007](https://github.com/kubescape/kubescape/issues/3007) documented
  multiple controls sharing JUnit identities. That issue is completed; it is
  historical evidence for this failure class, not an unresolved bug claim
- [GitLab's current docs](https://docs.gitlab.com/ci/testing/unit_test_reports/)
  warn that duplicate test names can make results disappear during ingestion

This project audits generated artifacts; it does not replace upstream fixes.
[Research and alternatives](docs/research.md) explains the narrow scope.

## Limits and privacy

Supported: a `testsuite` root, a `testsuites` root containing suites, nested suites,
and consistent namespaces. DTDs and custom entities are rejected. External entities
are never resolved. Parsing is streamed; failure bodies, logs and attachment content
are not retained or emitted. Output does include filenames, suite names and test
identities, which can themselves be sensitive. Review before sharing.

Defaults: 32 MiB per file, 128 MiB per run, 200,000 cases per run, 1,000 files,
64 XML levels, 4,096 characters per identity component. Custom API `Limits` may
raise or lower these limits. This is not an XML schema validator, a test runner,
a report merger, or a resource-isolation sandbox. See [SECURITY.md](SECURITY.md).

## Development

```sh
python -m unittest discover -s tests -v
python scripts/demo.py
python -m compileall -q junit_collision_check
```

Tests cover multi-file collisions, valid adjacent controls, scopes, namespaces,
UTF-16, invalid reports, DTD/entity rejection, limits, CLI exit codes, privacy and
unchanged inputs. CI runs the suite on Linux, macOS and Windows with Python 3.12,
3.13 and 3.14. Hosted results are visible in the Actions tab; a workflow definition
alone is not evidence of a passing run.

[Contributing](CONTRIBUTING.md) · [MIT license](LICENSE)
