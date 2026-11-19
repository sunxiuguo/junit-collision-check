# Keep distinct link occurrences visible

These independently authored fixtures model two failed occurrences of one URL in
different source documents. They are synthetic, not output captured from lychee or
GitLab. No producer, network service, or CI report consumer runs in this example.

## Before and after

From the repository root:

```sh
python -m junit_collision_check examples/link-occurrence/repeated-link-before.xml
# Expected audit exit: 1

python -m junit_collision_check examples/link-occurrence/repeated-link-after.xml
# Expected audit exit: 0
```

The before fixture has two testcase records with the same name and no classname.
Their `file` and `line` attributes differ. The default audit identity is still the
same exact pair: empty classname plus name. Expect two records, one unique identity,
and one `DUPLICATE_IDENTITY` collision group.

Both records report failure, so `potential_hidden_failure` is false. There is no
conflicting-outcome claim. A consumer that keeps only one duplicate can lose an
occurrence even when its retained record also fails.

The after fixture includes the source document and position in each testcase name.
Expect two unique identities and no collision. **Both tests still report failure.**
Audit exit 0 means no identity collision; preserve your link checker's failure gate.
The auditor never changes either input or selects a winning record.

Both occurrences are in one suite in one report. Changing to `--scope file` or
`--identity suite-class-name` therefore does not remove the before collision.
Report-file scope does not use testcase `file` attributes. Collision occurrences
point to the input XML report and XML line, not those source-document attributes.

For machine-readable output, append `--format json` to either command.

## Source and limits

[lychee #2302](https://github.com/lycheeverse/lychee/issues/2302) reports duplicate
JUnit names for repeated links in different files, causing later occurrences to
disappear in GitLab. Checked 2026-10-07: the issue remains open, and the existing
[upstream fix #2304](https://github.com/lycheeverse/lychee/pull/2304) is approved but
unmerged. This example does not replace or claim authorship of that fix.

In the inspected
[lychee master formatter](https://github.com/lycheeverse/lychee/blob/c11d7794e9be55fc57d5ffd35543bf6221799fb3/lychee-bin/src/formatters/stats/junit.rs),
names contain the outcome prefix and URL; file/line are separate attributes, and
classname is absent. The
[proposed upstream formatter](https://github.com/lycheeverse/lychee/blob/b32c1947b56bb8279fd9436b240d2f8f3dccc555/lychee-bin/src/formatters/stats/junit.rs)
uses source and available position in the name, removing the outcome prefix so the
same occurrence keeps its identity when its result changes.

This is an artifact-shape regression under the auditor's documented identity rules.
It does not establish installed lychee behavior, GitLab ingestion behavior, complete
coverage of producer cases, or that every expected link occurrence was emitted.
Do not combine unrelated runs just to compare identities: supply one intentional
result population to each audit.

The standard-library unit suite covers these fixtures, option behavior, separate
failure status, CLI exits, and unchanged fixture bytes. No new dependency is needed.
