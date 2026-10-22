# Audit real Playwright JUnit output

This optional example runs **Playwright 1.64.1** against a small synthetic HTTP
service on `127.0.0.1`, then checks its real JUnit XML with the installed auditor.
It uses two named **API-only** projects. It never launches a browser, downloads
browser binaries, contacts a real application, or imports production reports.

## Run

Use Node 20+ and Python 3.12+ with Expat 2.6.0+. From a reviewed repository
checkout, install the auditor in a virtual environment:

```sh
python -m venv .venv
.venv/bin/python -m pip install .
cd examples/playwright-api
npm ci --registry=https://registry.npmjs.org
../../.venv/bin/python probe.py --auditor-python ../../.venv/bin/python
```

On Windows, use the equivalent `.venv/Scripts/python.exe` paths. Installation
requires package-registry access. The three npm packages are pinned in the lock
file and have no install lifecycle scripts. Do not run `playwright install` for
this example. Playwright is an example-only dependency; the auditor still has no
third-party runtime dependencies.

The verifier starts a temporary loopback HTTP server, runs six bounded test
commands, audits their reports, and stops the server. Its child processes receive
only selected platform-path variables and fixed fixture settings, not the full
parent environment. Synthetic XML, audit JSON and logs are written to
`artifacts/`; those files are overwritten on another run. Each runner invocation
must create a fresh report, so a stale XML file cannot make a failed invocation
appear to have produced a report. The verifier also checks that audits leave XML
bytes unchanged.

## Expected results

| Control | Test runner exit | Audit exit | What is checked |
| --- | --- | --- | --- |
| Default JUnit, two projects | 0 | 1 | Four records contain two duplicate identities. |
| Project-prefixed names | 0 | 0 | Four distinct identities are retained. |
| One retry succeeds in each project | 0 | 0 | Two testcases contain two retry-metadata elements, not duplicate testcases. |
| One unique test finally fails | 1 | 0 | A clean identity audit does not turn a failed test green. |
| Two disjoint shards, prefixed names | 0, 0 | 0 | All four identities remain distinct across the two reports. |
| Accidentally combine full run and both shards | Already generated | 1 | Eight records repeat all four identities. |

The verifier exits 0 when these **expected synthetic outcomes** are established.
That is not a production gate. In production, preserve both exit statuses: any
test failure or audit failure must keep the combined gate failing. Do not replace
the test runner's exit code with the auditor's exit code.

## Use the existing reporter setting

Playwright's JUnit reporter defaults to `includeProjectInTestName: false`.
For a consumer whose identity is `(classname, name)`, pooling the same tests from
multiple projects can therefore collide, even though `testsuite.hostname`
contains the project name. If those projects belong in one combined population,
use the existing reporter option:

```js
reporter: [['junit', {
  outputFile: 'results.xml',
  includeProjectInTestName: true,
  includeRetries: true,
}]]
```

Alternatively, audit and ingest independent project populations separately.
Do not use separate filenames or suite labels to conceal overlapping shards in
the same population. This example uses the auditor's default `class-name`
identity and `all` scope; configure it to match your actual consumer.

The native retry representation stays inside one testcase, using
`flakyFailure`/`flakyError` or `rerunFailure`/`rerunError` children. The example
checks a successful retry, not every possible retry/error combination. It does
not infer a new ordering or rewrite those results.

## Sources and limits

- [Fixed Playwright reporter implementation](https://github.com/microsoft/playwright/blob/cfe490d941f992655948eee8fd4fd94e1c4234bf/packages/playwright/src/reporters/junit.ts)
- [Official multi-project and retry regression tests](https://github.com/microsoft/playwright/blob/cfe490d941f992655948eee8fd4fd94e1c4234bf/tests/playwright-test/reporter-junit.spec.ts)
- [Real multi-project report-loss report](https://github.com/microsoft/playwright/issues/27665), tracked in [#23432](https://github.com/microsoft/playwright/issues/23432)

The reporter already provides the project-name setting, and its retry support
is already implemented. This is a runnable consumer example, not a new
Playwright bug fix, replacement reporter or claim of external adoption.
No hosted GitLab/Jenkins ingestion, browser-engine execution, Playwright blob
merge, or live CI run is established by this local example. GitLab/Jenkins may
have consumer-specific identity rules beyond the default tuple used here.
