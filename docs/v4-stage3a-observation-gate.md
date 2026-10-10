# V4.0 Stage 3A: independent observation without Gate relaxation

Scope: existing Dashboard evaluator/renderer/trusted-main writer. This is a
read-only human-facing projection; it grants no external writes or dispatch.

* The current collected GitHub PR is checked for Issue Refs, repository,
  base=main and full HEAD before displaying bound facts. For merged PRs,
  merge SHA, merged_at and the human actor type must also be present.
* Existing CI/review/sync evidence evaluators are reused if their authenticated
  metadata is available. Unavailable or incomplete evidence remains PENDING.
* An absent initial implementation dispatch receipt still produces the old
  SAFE_STOPPED/BLOCKED formal state and never invents a run ID. It does not
  conceal separately observed PR details in the Markdown display.
* "INSPECT_BOUNDED_FACTS" is a read-only advisory, not a new policy field,
  credential, or machine Execution Gate. Other operations continue to require
  their existing authorizations and safety checks. No schema, policy, manager,
  automation, lease, workflow trigger, or Windows sync behavior is changed.
* Rendering is deterministic for unchanged collected facts. The writer retains
  its double-read, same-comment, NO_OP and post-write verification.
* When the trusted collection fails, the formal existing safe-stop still applies;
  there is no stale cached PASS or invented successful observation.

This PR deliberately does **not** implement I-07/I-09 consolidation. That is
Stage 3B after the present PR has been reviewed, human-merged and verified
against its actual main writer behavior.
