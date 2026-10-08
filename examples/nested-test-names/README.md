# Catch collisions after nested test names are shortened

These original synthetic fixtures model two distinct tests, `a.b.c.d` and
`a.b.c.e`, whose exported names have both become `[a; b; c; ... ]`. They model the
reported XML shape in [Expecto #534](https://github.com/haf/expecto/issues/534).
No Expecto executable, .NET runtime or CI report consumer runs in this example.

## Run the audit

From this repository root:

```sh
python -m junit_collision_check examples/nested-test-names/truncated-before.xml
# Exit 1: 2 records, 1 identity, CONFLICTING_OUTCOMES

python -m junit_collision_check examples/nested-test-names/unique-after.xml
# Exit 0: 2 records, 2 identities, no collision

python -m unittest discover -s tests -p test_nested_test_names.py -v
```

Both reports contain one failed and one passed test. The testcase records in the after fixture change
only their names. Audit exit 0 means their identities are distinct;
keep the test runner's separate failure gate.

The exporter shape has no `classname`, so the default identity is the pair
`("", name)`. The colliding records share one report and one suite. Neither
`--scope file` nor `--identity suite-class-name` recovers the missing segments.
The auditor identifies both XML locations; it cannot infer the lost test names.

The before fixture has conflicting outcomes. `potential_hidden_failure: true`
describes the risk of a consumer retaining a nonfailing duplicate. It does not
establish which result a real consumer retains. When both records pass, the
auditor still returns `DUPLICATE_IDENTITY`, without a potential-hidden-failure flag.

## Important negative control

```sh
python -m junit_collision_check examples/nested-test-names/single-truncated.xml
# Exit 0: one record has no other record to collide with
```

A name can be truncated yet unique in the supplied report. This tool does not
validate name formatting, recover original hierarchy, prove report completeness,
or compare names against an expected test inventory. Check exact emitted names
and expected counts in the producer's regression tests as well.

## Source and next validation

Checked 2026-10-08: [Expecto #534](https://github.com/haf/expecto/issues/534) is open.
The reporter describes version 10.2.3 and offers to contribute a fix. At inspected
main commit [`cec2c63`](https://github.com/haf/expecto/blob/cec2c63c8d77c6c21bf7e35d903020f74ddc1cea/Expecto/TestResults.fs#L148),
the JUnit writer passes `flatTest.name` directly to `XAttribute`, emits no classname,
and puts cases in one assembly-named suite. The NUnit writer uses the same name
conversion. This auditor supports JUnit, not NUnit reports.

The after fixture is a proposed distinct-name control. It is not output captured
from an upstream fix, proof that a released version is fixed, or adoption evidence.
The next producer-level check should generate reports from two sibling tests that
share three name segments and differ in the fourth, assert both full names, and
verify the same test outcomes remain present. Include the isolated truncated-name
case to keep the producer's name assertion separate from this collision audit.

No repair, report rewriting, retry inference, or upstream patch is included.
