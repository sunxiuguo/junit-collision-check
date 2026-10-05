# Contributing

Start with a small, synthetic failing report and the valid neighboring case.
Include the producer/version, consumer identity rules, expected behavior and a
public source where possible. Never attach production logs or secrets.

Run `python -m unittest discover -s tests -v` and `python scripts/demo.py`.
The project uses only the standard library at runtime and in its tests. Keep the
parser read-only and avoid guessing retry order. New dialect support must fail
explicitly for shapes it cannot interpret safely. Add focused tests for every fix.

The optional [pytest adoption example](examples/pytest-ci/) has its own pinned
requirements and verifier. It generates real XML from fixed synthetic tests;
pytest is not a dependency of the auditor or its standard-library unit suite.

The accepted scope is collision auditing. Transformations, network integrations,
arbitrary commands and secret-bearing fixtures are outside the initial release.
