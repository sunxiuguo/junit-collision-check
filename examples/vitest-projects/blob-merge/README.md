# Keep test identities distinct when merging Vitest blobs

In a CI matrix, each job can produce a blob report for the same test suite.
[Vitest #9954](https://github.com/vitest-dev/vitest/issues/9954) asked for one
merged report without collapsing environment-specific observations. The merged
[blob label feature](https://github.com/vitest-dev/vitest/pull/10031) addresses
retention. It does not set the project name that JUnit's `{displayName}` uses.

Use a distinct, stable blob label **and** a distinct, stable Vitest project name
per matrix job. With the JUnit reporter, set
`classnameTemplate: '{displayName}:{filename}'`. Keep the original failing
runner/merge status and audit the resulting XML separately.

## Replay

Use Node 24.22.3, Python 3.12 or newer with Expat 2.6.0 or newer, and an already
installed, reviewed Vitest 5.0.3 at `node_modules/vitest` in this directory.
From this directory run:

```sh
python3 verify.py ../../..
```

The argument is the root of the checker checkout. The verifier uses a temporary
folder with a fresh HOME and removes its generated reports. No model, database,
browser, or customer data is used.

| Blob merge control | Outcome count and identity audit |
| --- | --- |
| Separate labels; same project; default JUnit template | Both outcomes retained; collision |
| Separate labels; same project; project-prefixed JUnit template | Both outcomes retained; collision |
| Separate labels and project names; project-prefixed template | Both outcomes retained; distinct identities |

All three merges still exit 1 because one job deliberately fails. The verifier
also runs two direct XML controls to separate the JUnit template's effect
from blob merge behavior. An audit pass never changes a failed run to a pass.

This example uses the default auditor identity, `(classname, name)`. It does
not verify hosted consumers, or guarantee unique identities for a consumer
that ignores classnames or normalizes the keys differently.
