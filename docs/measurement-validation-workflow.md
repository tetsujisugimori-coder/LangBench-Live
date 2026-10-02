# Trusted-main Windows measurement validation

`measurement-validation-windows.yml` is the preparation path for Issue #74. It
has a parameter-free `workflow_dispatch` trigger and must be dispatched from
`main`. The hosted `authorize` job pins the current remote-main SHA, verifies a
unique human-merged pull request, and finds an official successful
`pull-local-main.yml` run whose repository, event, branch, SHA, and both jobs
match. If remote main moves during authorization, it stops rather than following
the new commit.

The merged PR commit may equal the target or be its ancestor. Authorization uses
the GitHub compare API and accepts only `identical` or `ahead`; `behind`,
`diverged`, and unknown states fail closed.

Only the authorized SHA reaches the runner with labels `self-hosted`, `Windows`,
`X64`, and `langbench-live-tetsu-windows`. The runner checkout is separate from
the user's working copy. The latter must already have been synchronized through
the official workflow; validation never synchronizes it. Its origin, branch,
HEAD, tracked state, Git-operation markers, untracked/ignored files, and remote
main are checked. The shared operation and measurement locks are held while a
new, collision-refusing independent clone executes the existing Count=1 path
with its own distinct operation and measurement locks. The shared
copy is not reset, cleaned, stashed, rebased, or written.
Effective Git content filters are rejected before status inspection. Git output
is decoded as UTF-8 and system attributes are disabled for each hardened command
without changing persistent Git configuration.

The run uses one `direct_first` repetition of the existing
`function_call_numeric_sum` benchmark. It does not use the 12-run balanced-order
mode and does not alter benchmark inputs, compilation, or measurement semantics.
The evidence bundle contains the formal `measurement-manifest-v2.json`, archive
index and experiment definition, archive-reader/validator status, manifest-v2
exact-applicability controls, run and synchronization identity, a human-readable limitation, and SHA-256
values for each included file. Raw results stay in the ephemeral runner checkout
and are not uploaded. The artifact name and directory include Issue, Actions run
ID, attempt, and trusted SHA. Failed generation is not uploaded as a successful
bundle.

The matching and missing/mismatch/unknown controls are derived in memory from the
validated manifest. Their complete order-coverage input is explicitly synthetic.
They demonstrate comparator behavior only—not observed optimization analysis,
order coverage, or performance. Legacy archive comparison is recorded separately
without upgrading missing/caution. Every output is rejected before upload if the
existing artifact-safety scanner detects credentials or private absolute paths.
The bundle-specific scan additionally rejects signed or credential-bearing URLs.
The Actions artifact ZIP digest is intentionally
different from the listed hashes of files inside it; actual ZIP download and
integrity verification remain the post-merge Issue #73 task.
