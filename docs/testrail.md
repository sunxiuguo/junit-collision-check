# Optional TestRail auto-matcher identity preflight

`python -m junit_collision_check examples/testrail/collision.xml --identity testrail`

This opt-in, read-only profile checks effective automation IDs before a **standard
JUnit auto-matcher** upload. The generic `(classname, name)` default is unchanged.
It neither uploads reports nor predicts server overwrite/history behavior. Supply
only reports intended for the same TestRail matching population; use `--scope file`
only when files intentionally represent independent populations. Suite names do
not partition this profile's identity groups. BDD grouping, name/property manual
case-ID matchers, global field overrides, alternate automation-field configuration,
and server/project matching configuration are not modeled. Those options are not
encoded reliably in XML: the caller must select this mode only for the stated
configuration. A clean result is not import success or proof that tests passed.

## Pinned behavior and evidence

Source: [Gurock TR CLI junit_xml.py](https://github.com/gurock/trcli/blob/ff097e41f6abe177c73b229bf5211eb1fb856e7b/trcli/readers/junit_xml.py),
[FieldsParser](https://github.com/gurock/trcli/blob/ff097e41f6abe177c73b229bf5211eb1fb856e7b/trcli/data_classes/data_parsers.py),
and [TestRailCase normalization](https://github.com/gurock/trcli/blob/ff097e41f6abe177c73b229bf5211eb1fb856e7b/trcli/data_classes/dataclass_testrail.py).
Observed November 15, 2026. The actual pinned parser was exercised offline with
synthetic XML using Python 3.12.14, click 8.5.1, junitparser 3.2.0, pyserde 0.12.7
and installed versions satisfying its complete runtime dependency declarations.
No server imports, customer data, adoption or revenue were verified.

Supported precedence:
1. Last `property name="testrail_case_field" value="custom_automation_id:VALUE"`
   wins among these properties.
2. A truthy property VALUE wins; otherwise use the `custom_automation_id`
   testcase attribute if present, or `classname.name` if absent.
3. Strip surrounding whitespace from the selected string **after** choosing it.

An empty property falls back; whitespace-only property wins then becomes empty.
An explicitly empty attribute remains empty. Empty effective IDs produce
`EMPTY_TESTRAIL_ID` (invalid input), not a fabricated usable identity. Different
JUnit tuples can share an effective ID; identical tuples can have distinct
explicit IDs. Existing explicit stable overrides already resolve the dot-join
ambiguity. The profile does not rewrite IDs or recommend migrating existing IDs.

## Deliberately narrow input boundary

Require non-namespaced flat, explicitly named suites and explicit nonempty
classname/name. Support string-valued legacy automation-ID attributes and exact
property names above, direct ordinary terminal result elements and output text.
Reject nested suites, retry extensions, suite properties, unknown properties or
attributes, modern `custom_case_automation_id` fields, suffixed case-field names,
text-valued properties, missing property values and bracket-start property values.
These may have meaningful upstream behavior; rejecting them avoids silently
mis-modeling it. No literal evaluation is performed. DTD/entity and existing
byte/depth/case/identity bounds remain in force.

Reports expose a SHA-256 effective-ID key, not raw override values. Source paths
and suite names remain visible as in other modes; use synthetic/redacted inputs
when sharing output. XML output and failure messages are never retained.

Run `python examples/testrail/verify.py` for a collision and its explicit-override
neighbor. These are labeled synthetic demonstrations, not user adoption evidence.
