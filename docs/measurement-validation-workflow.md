# Trusted-main Windows measurement validation

`measurement-validation-windows.yml` is the preparation path for Issue #74. It
has a parameter-free `workflow_dispatch` trigger and must be dispatched from
`main`. The hosted `authorize` job pins the current remote-main SHA, verifies a
unique human-merged pull request, and finds an official successful
`pull-local-main.yml` run whose repository, event, branch, SHA, and both jobs
match. If remote main moves during authorization, it stops rather than following
the new commit.

Only the authorized SHA reaches the runner with labels `self-hosted`, `Windows`,
`X64`, and `langbench-live-tetsu-windows`. The runner checkout is separate from
the user's working copy. The latter must already have been synchronized through
the official workflow; validation never synchronizes it. Its origin, branch,
HEAD, tracked state, Git-operation markers, untracked/ignored files, and remote
main are checked. The shared operation lock is held while the runner checkout's
existing Count=1 path takes its own operation and measurement locks. The shared
copy is not reset, cleaned, stashed, rebased, or written.

The run uses one `direct_first` repetition of the existing
`function_call_numeric_sum` benchmark. It does not use the 12-run balanced-order
mode and does not alter benchmark inputs, compilation, or measurement semantics.
The evidence bundle contains the manifest v2, archive-reader/validator status,
comparison controls, run identity, a human-readable limitation, and SHA-256
values for each included file. Raw results stay in the ephemeral runner checkout
and are not uploaded. The artifact name and directory include Issue, Actions run
ID, attempt, and trusted SHA. Failed generation is not uploaded as a successful
bundle.

The matching and negative controls are derived in memory from the validated
archive. They demonstrate comparator behavior only—not optimization analysis,
order coverage, or performance. The Actions artifact ZIP digest is intentionally
different from the listed hashes of files inside it; actual ZIP download and
integrity verification remain the post-merge Issue #73 task.
