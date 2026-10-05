# Keep test failures and identity collisions as separate gates

This optional example generates real JUnit XML with **pytest 9.1.1**, then audits
the resulting files. The tests and their data are synthetic. It does not download
reports, run your project's tests, or reproduce a claimed pytest bug.

## Run the four controls

Use Python 3.12+ with Expat 2.6.0+, as required by the auditor. From the repository
root, inside a virtual environment:

```sh
python -m pip install -r examples/pytest-ci/requirements.txt
python examples/pytest-ci/demo.py
```

The installation needs package-index access. After installation, the demo needs
no network or credentials. pytest is an example-only dependency; the auditor's
runtime and its existing unit tests remain standard-library-only.

The demo executes only two fixed test functions in a temporary directory. It
isolates pytest configuration, disables external plugin autoload, and removes
the temporary files on exit. It checks that auditing leaves every XML file
unchanged and rejects an expanded environment representation or synthetic
environment sentinel in each report. This guards the fixed fixture; it is not a
general-purpose secret scanner.
The intentional failure asserts a local boolean, so pytest's assertion details
do not expand the process environment into the XML.

| Case | pytest exits | Audit exit | Combined production gate |
| --- | --- | --- | --- |
| Disjoint shards: different tests | 0, 0 | 0 | Pass |
| Unique failed test | 1 | 0 | **Fail** |
| Overlapping shards: same passing test twice | 0, 0 | 1 | **Fail** |
| Accidentally combined failed/passed attempts | 1, 0 | 1 | **Fail** |

Each row is asserted against the real CLI. Overlapping shards must produce one
`DUPLICATE_IDENTITY`; conflicting attempts must produce one
`CONFLICTING_OUTCOMES` with a potential-hidden-failure flag. Unexpected pytest
exits, missing reports, invalid XML, wrong counts or changed files fail the demo.

The demo itself exits 0 when those **expected example outcomes are verified**.
That is a self-test of the example, not a production test gate. In particular,
the unique failed test produces a clean identity audit while its test gate must
remain failed.

## Minimal GitHub Actions recipe

Assumptions: your application and pytest are already installed, and a reviewed
commit of this auditor is checked out at `tools/junit-collision-check`. These
steps belong to one OS/Python result population. Replace `tests` with your own
test selection and keep the normal runner exit status:

```yaml
- name: Run application tests
  run: python -m pytest tests --junitxml=test-results/junit.xml

- name: Audit this population's report identities
  if: ${{ !cancelled() }}
  run: python tools/junit-collision-check/scripts/check_reports.py 'test-results/**/*.xml'
```

Use neither `continue-on-error` nor `|| true` on either step. The audit still runs
after a test failure, and a successful audit cannot undo the failed test step.
If no report was written, the unmatched input is an audit error rather than a
false clean result. The example does not implement artifact uploads; preserve
reports with your existing post-failure artifact policy and appropriate access.

GitHub gives ordinary steps an implicit success condition. The explicit
`!cancelled()` condition lets the audit run after a failure without continuing
after cancellation. If a more complex workflow uses `continue-on-error`, note
that a failed step's `conclusion` becomes `success`; its `outcome` still records
`failure`. Do not build a test gate from the softened conclusion.

For separate jobs, retain both the test job and audit job as required checks.
An audit job depending on a failed test job also needs an explicit post-failure
condition. This snippet covers a single job, not artifact aggregation across jobs.

## Keep matrix populations separate

The two overlapping reports deliberately have **different suite labels and
filenames**. Their default `(classname, name)` identities still collide. Renaming
artifacts or changing `junit_suite_name` does not fix an overlapping shard.

Conversely, running the same tests on two independent OS/Python configurations
is legitimate. Audit all shards of each configuration together, with a separate
invocation for each independent population. Do not pool every matrix artifact
into one default audit, or use `--scope file` to hide overlap between shards that
actually belong to one population.

## Evidence and verification limits

- [pytest JUnit output](https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files)
- [pytest exit codes](https://docs.pytest.org/en/stable/reference/exit-codes.html)
- [pytest 9.1.1 release](https://pypi.org/project/pytest/9.1.1/)
- [GitHub step outcome and conclusion](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#steps-context)
- [GitHub status-check functions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#status-check-functions)
- [GitHub job dependencies](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idneeds)

The `pytest-example` CI job checks generated XML and the four expected exit-code
combinations. It does not exercise a deliberately failing production workflow or
prove a particular downstream JUnit consumer's deduplication behavior. The
production recipe follows GitHub's documented step semantics.
