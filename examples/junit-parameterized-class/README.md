# Audit a JUnit producer upgrade with real XML

This optional example generates legacy XML from **original synthetic Java tests**
using two fixed JUnit Console Standalone versions. It verifies both the historical
collision and a fixed-version control. No XML or Java from an issue is copied.

## The workflow and its limits

A team publishing JUnit Jupiter legacy XML can audit the generated artifact after
the test runner, then check whether a producer upgrade removes identity collisions.
[JUnit #5409](https://github.com/junit-team/junit-framework/issues/5409) reported
parameterized-class invocations sharing `(classname, name)` in 6.0.3. The issue is
**closed/completed**, not a current unresolved bug. It was checked on 2026-11-14.

Our six passing tests produce two identities in 6.0.3, but six identities in
6.1.3. This is evidence for a historical producer failure class and an upgrade
regression check, **not evidence that current JUnit is broken, that anyone uses
this auditor, or that a separate paid product is needed**. Prefer fixing or
upgrading the producer when possible. This verifier is not an automatic migration.

[GitLab's documentation](https://docs.gitlab.com/ci/testing/unit_test_reports/)
warns that duplicate tests can be omitted from reports. This example does **not**
upload to GitLab or verify a hosted consumer. Nor does it establish all consumer
identity rules. The auditor uses its default exact `(classname, name)` identity.

## Run

Requires Python 3.12+ with Expat 2.6.0+ and a **full JDK 17+** (the `jdk.compiler`
module is used). No Maven, Gradle, Python dependency, account or credentials are
needed. Review the Java source and verifier before execution.

Download these exact artifacts from Maven Central yourself, outside this checkout:

- [JUnit Console Standalone 6.0.3](https://repo.maven.apache.org/maven2/org/junit/platform/junit-platform-console-standalone/6.0.3/junit-platform-console-standalone-6.0.3.jar)
- [JUnit Console Standalone 6.1.3](https://repo.maven.apache.org/maven2/org/junit/platform/junit-platform-console-standalone/6.1.3/junit-platform-console-standalone-6.1.3.jar)

The verifier checks both SHA-256 digests **before executing either JAR**:

```text
6.0.3  3ba0d6150af79214a1411f9ea2fbef864eef68b68c89a17f672c0b89bff9d3a2
6.1.3  e62b96ac475dbcde8599ea905d088f65d90778f86e259b856a49fa5c4ea256ec
```

From the repository root:

```sh
python examples/junit-parameterized-class/verify.py \
  --jar-6-0-3 /path/to/junit-platform-console-standalone-6.0.3.jar \
  --jar-6-1-3 /path/to/junit-platform-console-standalone-6.1.3.jar
```

It compiles and runs only `BatchSizeTest`, generates reports in an isolated temporary
directory, calls the existing auditor CLI, and verifies:

| Version | Test runner exit | Test records | Identities | Collision groups | Audit exit |
| --- | --- | --- | --- | --- | --- |
| 6.0.3 | 0 | 6 | 2 | 2 | 1 |
| 6.1.3 | 0 | 6 | 6 | 0 | 0 |

Both runs must contain six passing cases. The verifier itself exits 0 only when
both expected results hold. No test failure is hidden with `|| true`. The historical
case contains no mixed outcomes, so `potential_hidden_failure_groups` is 0.
Temporary reports and classes are removed on completion. Output is a count/exit
summary, not environment properties from the XML. The script never downloads
artifacts, rewrites input reports or contacts a CI service.

Observed locally on 2026-11-14 with Python 3.12.14 and OpenJDK 21.0.13. Other
platforms are not claimed tested. These pinned versions are deliberate controls,
not an instruction to downgrade production or a promise of future compatibility.

## Licenses and privacy

The Java fixture and verifier are original contributions under this repository's
MIT license. No JARs, third-party source, issue XML or generated environment
properties are committed here. JUnit's published POM declares EPL-2.0; the
standalone distribution includes its own third-party notices. Obtain artifacts
from their official source and retain those notices. The test data is only three
integers; do not substitute production data or upload generated reports without
reviewing their environment metadata.
