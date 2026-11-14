# Keep Vitest project identities distinct

When two named Vitest projects run the same file and test title, default JUnit
output can give both records the same `(classname, name)`. A downstream consumer
using that identity may keep only one. This example shows a built-in producer
configuration and checks the boundary without installing anything.

## Offline audit

From the repository root:

```sh
python -m junit_collision_check examples/vitest-projects/default.xml
# Expected exit 1: two records, one identity, one collision group.
python -m junit_collision_check examples/vitest-projects/distinct.xml
# Expected exit 0: two records, two identities, no collisions.
python -m junit_collision_check examples/vitest-projects/distinct-failure.xml
# Expected exit 0: four distinct identities, despite one failed test.
python -m unittest discover -s tests -p test_vitest_example.py -v
```

The XML files are deterministic, minimized **synthetic illustrations** of the
observed shapes, not raw runner output. Timing, hostnames and local paths are
omitted. The last fixture contains one success, one failure and two skips: a
clean identity audit must never replace the test runner's failure gate.

## Native producer configuration

The experiment used **Node 24.22.1 and Vitest 5.0.3**. The bundled
`vitest.config.mjs` contains the two synthetic projects and this reporter option:

```js
reporters: [['junit', {
  outputFile: 'generated.xml',
  classnameTemplate: '{displayName}:{filename}',
}]],
```

`displayName` is the Vitest project name. With this fixture, the classes become
`project-a:same.test.js` and `project-b:same.test.js`, while the leaf test names
remain identical. Give projects distinct, stable names. This is a configuration
for these identities, not a proof that arbitrary delimiter-joined names are
collision-free. Keep auditing the actual reports your consumer receives.

To regenerate with an **already installed, reviewed Vitest 5.0.3** and Node
24.22.1, enter this example directory and run its existing `vitest` executable:

```sh
vitest run --config vitest.config.mjs
# Expected runner exit 0; generated.xml contains both project identities.
python ../../scripts/check_reports.py generated.xml
# Expected auditor exit 0.
```

Removing `classnameTemplate` from a temporary copy of the configuration generates
the default collision control. The fixture runs no browser, network request or
customer test. No installer, automatic download or dependency lockfile is
provided; check both tool versions yourself rather than silently using `latest`.

## Actual consumer check and its limits

On 2026-11-14, native reports were also passed through **python-subunit 1.4.6**
`junitxml2subunit` and loaded into independent empty **Inquest 0.3.6** repositories.
The consumer source was `53bd95bc708b5ae47a433c485f2a75b90e146d29`.
The converter uses `classname::name`; the tested database keys records by run
and test ID.

| Native input | Stored records |
| --- | --- |
| Default, two passing projects | 1 success |
| Project-prefixed, two passing projects | 2 successes |
| Project-prefixed mixed control | 1 success, 1 failure, 2 skips |

Independent repetitions checked stored rows, not just console totals. Inquest's
mixed-run console displayed `Passed: 3`, including the two skips; that was not
three successful test executions. The supplied offline audit does **not** rerun
these optional tools or certify other releases and hosted consumers.

This is not a complete Vitest/Inquest integration recipe. A simple report-producing
command did not implement Inquest's listing/selection protocol: `--failing` still
executed both projects. Imported streams lacked commit provenance. Fresh-report
checks, targeted reruns, retries and meaningful same-commit flakiness analysis
need separate validation. Do not select a different auditor scope just to hide a
collision, and do not assume report order identifies retries.

## Sources

- [Vitest reporter documentation](https://vitest.dev/guide/reporters), including
  JUnit templates and file output.
- [Inquest 0.3.6](https://github.com/jelmer/inquest/releases/tag/v0.3.6), the tested
  consumer release.
- [python-subunit 1.4.6](https://pypi.org/project/python-subunit/1.4.6/), the tested
  converter release.

These are synthetic compatibility results, not user adoption, lost production
data, or evidence that every multi-project report is broken.
