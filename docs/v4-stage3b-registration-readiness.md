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
