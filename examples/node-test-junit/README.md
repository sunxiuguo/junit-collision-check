# Audit JUnit reports from `node:test`

This optional example runs Node's built-in JUnit reporter against synthetic
tests. It checks the report dialect before treating a collision result as
meaningful. It does not change the checker or rewrite XML.

## Run the controls

From a checkout containing this example, use **Node 24.22.3** and Python 3.12+
with Expat 2.6.0+. The example has no package-install, network, or credential
step:

```sh
python examples/node-test-junit/verify.py
```

| Native Node input | Node exit | Default audit exit | GitLab profile exit | Test-and-audit gate¹ |
| --- | ---: | ---: | ---: | ---: |
| Top-level tests, one pass and one fail | 1 | 2 | 2 | 1 |
| Distinct named suites, both pass | 0 | 0 | 0 | 0 |
| Distinct named suites, one pass and one fail | 1 | 0 | 2 | 1 |
| Same named suite and test, one pass and one fail | 1 | 1 | 2 | 1 |
| Same named suite and test, both pass | 0 | 1 | 1 | 1 |

¹ Using the default audit. The verifier exits 0 when it observes all of the
expected controls, not because all of the synthetic tests passed.

On the tested Node version, top-level `test()` calls can emit `<testcase>`
directly under `<testsuites>`. The checker returns `UNSUPPORTED_STRUCTURE`
for that output, whether tested as one report or as separate files. Do not
interpret exit 2 as a clean audit. Wrap tests in distinct, meaningful
`describe()` suite names, such as the package name, and check that the
resulting `classname` values are distinct where the downstream consumer
requires them. Different file paths alone do not separate identities in
the default `(classname, name)` audit. Reusing the same suite name still
collides.

The opt-in GitLab profile is deliberately narrower. In this fixture it
rejects Node's `failure=` testcase attribute even inside a named suite
(`UNSUPPORTED_GITLAB_PROFILE`). These are checker results, not results
from a live GitLab job. Do not substitute the default identity mode for
a claim about what GitLab will show.

## Keep the two exit statuses

Use this pattern in a Linux/POSIX CI job from your application root, after
adopting named suites. Replace `tests/*.test.mjs` with your test selection.
Assumes a reviewed checker checkout at `tools/junit-collision-check`:

```sh
report_dir=$(mktemp -d) || exit 2
test_status=0
node --test --test-reporter=junit tests/*.test.mjs > "$report_dir/node.xml" || test_status=$?
audit_status=0
python tools/junit-collision-check/scripts/check_reports.py "$report_dir/node.xml" || audit_status=$?
printf 'node exit: %s; identity audit exit: %s\n' "$test_status" "$audit_status"
if [ "$test_status" -ne 0 ]; then
  exit "$test_status"
fi
exit "$audit_status"
```

The audit runs even when tests fail. A clean audit cannot turn a test
failure into a passing job. If you retain or upload reports, apply your
existing artifact policy; Node can include file paths, hostnames, and
failure details. The verifier keeps its generated reports in a temporary
directory and never prints their raw contents.

See the [Node JUnit reporter documentation](https://nodejs.org/api/test.html#test-reporters)
and the [suite classname change](https://github.com/nodejs/node/pull/60220).
