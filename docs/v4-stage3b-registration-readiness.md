# V4.0 Stage 3B — I-07/I-09 registration readiness from existing input

**This is an opt-in local advisory, not a Work registration API or Gate update.**

The v1 startup input is generic and stores only the independent review automation ID.
The v2 contract supports review and owner-resume, but is deliberately restricted
to the I-01 purposes. This change does not silently generalize that contract.

Run `tools/startup_preparation.py` with its existing input, state and output
options, plus `--registration-readiness`. It adds a single
`registration_readiness.json` derived from the **same validated input and
optional existing owner-facts**. Without the flag, original outputs are unchanged.

The report includes Issue/purpose/input digest, PR/HEAD when represented by the
approved v2 input, review/resume role and ID, approved Prompt digest/events
when represented, owner-reported settings/readback status, event observation,
and the next owner check. It **never** sets `formal_gate_authorized`,
`registration_performed` or `work_service_run_verified` to true.

For v2, the `owner_settings_matched` advisory requires both a full readback
matching the approved Prompt/Trigger and acceptance by the existing
`resume()` state history (`owner_watermarks`, input digest, timestamps,
settings revision, conflict flags and negative observations). A standalone raw
owner-facts object is un-reconciled and cannot certify current readiness.
A rejected older success never supersedes the latest negative observation.
The local report distinguishes the latest supplied observation from the
effective retained status; its next action remains reconciliation when they
conflict.

At `FINISHED`, both dedicated roles require `DISABLED_CONFIRMED`, saved
`enabled=false` and the existing stop readback rules. Enabled registrations
are **not** considered ready at closure. A verified disabled registration
is described as stopped, never as something to continue using. This advisory
does not certify the separate full-cycle Completion Gate or Work run.

A supplied owner-facts file must already pass the existing v1/v2 validator.
If v2 `--github-read` is in use, use the shared authenticated owner-facts
readback already obtained by the CLI. The local report is not written to
GitHub, does not call the Work API, and cannot grant a Merge/Completion PASS.
Incomplete saved trigger details remain unconfirmed. An old/current HEAD
change requires correct new binding and may not inherit approved results.

Future integration work may reduce real registration steps **only after**
the official Work interface exposes those operations and their readback.
This Stage 3B change intentionally preserves the Issue102-specific manager,
v1/v2 schema, policy, sole writer, existing denial history, and all
Windows sync protections. It does not modify PR #105's completed results.

## Reading reports after an unsuccessful CLI invocation

A generated `registration_readiness.json` is a **local advisory for the
specific invocation**, not a success signal on its own. If the next CLI run
stops or exits nonzero, a previously generated report can remain at the
same output path. Its presence, nonempty contents, or an earlier
`owner_settings_matched=true` do **not** override the failed run.

A consumer must check the current process exit status first, and inspect
the current preparation status and input digest when present, before using
any output. On a nonzero exit, discard that run's report as evidence even
if the file exists. A failure before state persistence may also leave an
old cache: absence of a newly written `STOPPED` field is not success.
Recheck authenticated current facts rather than reusing a previous positive
observation. Do not use these local files as Work event-delivery, task-start,
formal Merge Gate or Completion Gate evidence.
