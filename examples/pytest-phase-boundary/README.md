# One pytest test, two JUnit records

A collision is an observation about exported identity, not proof that two
independent tests were executed. This synthetic example reproduces a producer
boundary with **pytest 9.1.1**, the version pinned by this project's pytest
examples. It does not claim that this is the latest available pytest release.

Observed on 2026-11-14 in an isolated cloud environment:

| Synthetic input | Exported records | Auditor result |
| --- | --- | --- |
| One test whose call fails and fixture teardown errors, xunit2 | Same identity, failure + error | `CONFLICTING_OUTCOMES`, exit 1 |
| Two parameterized items intentionally given the same XML identity, xunit1; first call fails, second passes then teardown errors | Same identity, failure + error | `CONFLICTING_OUTCOMES`, exit 1 |

`CONFLICTING_OUTCOMES` here means different XML outcome tags, not a
contradictory pass/fail verdict. Both pytest runs exit 1. Both records carry failing outcomes; the auditor does
not claim a potential hidden failure in either case. The second example uses
pytest's experimental `record_xml_attribute` fixture with xunit1 deliberately
to simulate lossy identity customization. It is a control, **not recommended
configuration**, and emits pytest's experimental-fixture warning.

The outcome pair alone cannot establish whether records are phases of one test
or distinct tests sharing an exported name. File/line attributes and failure
text also depend on producer configuration and are not a universal provenance
contract. Do not automatically suppress all failure/error pairs, count collision
groups as distinct logical tests, or discard either failing result. Inspect the
runner's collected items and producer configuration before deciding what needs
repair. This example adds no suppression and changes no auditor behavior.

Historical context: [pytest issue #9909](https://github.com/pytest-dev/pytest/issues/9909)
is closed. Its closure does not establish that the yield-fixture scenario here
is absent in every later release. This is a bounded current-pin reproduction,
not a claim about all pytest versions, producers, or hosted CI rendering.

## Reproduce

From the repository root, in an isolated virtual environment:

```sh
python -m pip install -r examples/pytest-phase-boundary/requirements.txt
python examples/pytest-phase-boundary/verify.py
```

The verifier generates synthetic tests in a temporary directory, disables
third-party pytest plugin autoload, uses a local empty pytest configuration,
checks runner and auditor exit codes, XML identities/outcomes, and classification.
It deletes temporary reports rather than committing hostname/path-bearing raw
XML. It is not a wrapper for production tests. Expected output records two
`CONFLICTING_OUTCOMES` results with runner and auditor exits both 1.
