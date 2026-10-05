# Security and privacy

The CLI reads explicit local regular files and prints diagnostics. It makes no
network requests, starts no subprocesses, and does not write or repair reports.
It rejects DTDs and custom entities, never resolves external entities, streams XML,
and imposes byte, depth, case, identity and file-count limits.

Use a current patched Python interpreter. Expat below 2.6.0 is rejected because
old parsers have known resource-exhaustion weaknesses. Limits reduce risk but are
not a sandbox; apply process time/memory limits for deliberately hostile inputs.
Filesystem input paths and glob patterns are caller-controlled. Do not expose the
CLI as a public file-reading web service.

Reports omit test logs, failure text and attachment contents. They still expose
source paths, test names and suite names. Do not upload diagnostics publicly without
checking those fields. Unknown metadata and suite counters are outside the audit.

To report a vulnerability, use GitHub's private vulnerability reporting if enabled.
If it is unavailable, open an issue asking for a private contact without including
sensitive details or an exploit. No response-time guarantee is offered.
