# Boundary: identities already merged by the producer

`clean` means no duplicate identities were found in the parsed testcase records.
It does **not** certify that every executed test survived reporting, that the
producer preserved identity, or that the test run passed.

## Observed producer experiment

On 2026-11-14, a local synthetic experiment used Gradle 9.7.1 and JUnit 6.1.3.
Two different parameterized methods (`capacity` and `evenSize`) used the same
argument `2` and therefore the same leaf display name. `capacity` failed;
`evenSize` passed. No retries or retry plugin were configured. With
`reports.junitXml.mergeReruns = true`, Gradle reported **2 tests, 1 failure** and
**failed the build**, but its XML contained **one testcase with flakyFailure**.
The checker at `047ee676` returned exit 0, zero collisions, and
`cases_with_retry_metadata: 1`. The distinction had already been erased.

Controls: two methods with two values and all tests passing retained all four
rows. When one of those four tests failed, XML retained three rows; the checker
still flagged the other duplicate pair. Thus enabling merging does not collapse
all duplicate passing rows.

The tests were compiled with the JDK compiler module and supplied to Gradle's
real Test task as precompiled classes. This was not validation of Gradle's Java
compilation task or hosted CI ingestion. No CI false-green is claimed.

## Inspect the limitation locally

`merged.xml` is an intentionally minimized synthetic illustration of the shape,
not raw output or a general XML schema example. It contains no hostnames, paths,
production logs or third-party test data.

From the repository root:

```sh
python examples/gradle-merged-boundary/verify.py
```

Expected: the auditor reports clean/exit 0 but records retry metadata. That
metadata is **not proof of a collision**: legitimate retries use it too. A suite
count mismatch alone is also not proof because reporting dialects differ.

Keep test-runner exit status and producer-specific evidence alongside this
artifact audit. Do not blindly disable merging: it changes legitimate retry
reporting semantics. Validate the complete producer-to-consumer workflow before
choosing that configuration. The auditor cannot reconstruct identities absent
from its input, and it does not rewrite reports.

## Sources and next validation

- [Gradle reporting documentation](https://docs.gradle.org/current/userguide/java_testing.html#sec:configuring_java_test_reporting): merging is off by default,
  groups by reported test name, and does not itself perform retries.
- [Gradle #39079](https://github.com/gradle/gradle/issues/39079): real user report
  about parameterized method/class identities, including a grouping hypothesis.

A real hosted consumer run and legitimate retry controls remain untested here.
These results establish a scope limit, not adoption, revenue, or a universal
recommendation to change Gradle settings.
