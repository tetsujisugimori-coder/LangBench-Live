# CPU B elapsed-time repeat plan

## Frozen before the new measurements

- Main commit: `f72c582e274e928ac3f19b4ca9417de0a3327dfe` (PR #56 merge commit; confirmed equal to GitHub `origin/main` ref before the measurement).
- Repeat group: `repeat-20260929_091948-2ad7b1ff` (fixed before samples; reused after the compile-only preflight failure below).
- New experiment count: exactly 3 independent experiments, 120 complete cycles each when successful.
- Runner: existing `tools/repeat_cpu_pair.py` calling `tools/diagnose_c_affinity.py`, then existing `tools/compare_cpu_pair_runs.py` and `tools/analyze_cpu_pair.py`.
- Pair: candidate type `same_core_siblings`, expected CPU A=0 / CPU B=1 in processor group 0; stop before measurement if the existing topology candidate or affinity checks do not resolve that pair.
- Benchmark: C / `function_call_numeric_sum`, C/direct samples; input count 1,000,000; warmup 5; 50 samples per run; direct then function_call; GCC flags `-O2 -std=c11 -Wall -Wextra`; affinity as the configured run difference; balanced ABBA cycle order.
- CPU monitor: retain the existing per-run system-wide busy observations and QPC overlap metadata.
- Experiment IDs: generated independently by the existing runner in its timestamp format; each run must have a distinct ID. The repeat group ID above is shared by all three.
- Outcome handling: preserve failed or incomplete runs and report them as missing; do not add repetitions or change the analysis criteria after seeing any result.
- Analysis: analyze each experiment separately; no elapsed-time series concatenation. Report elapsed Pearson r, complete-cycle first-half/second-half run-median medians and difference, order and position summaries, existing outlier sensitivity, and busy-monitor coverage/association for CPU A and B.
- Existing comparison inputs: PR #56's four published experiments in `artifacts/cpu-pair-b-time-repro/public-data.json` (including old 30-cycle, older 120-cycle and prior 2×120-cycle group), plus the separate local 30-cycle experiment `results/diagnostics/cpu-pair-independent-repeat-30-20260928` and the complete same-day two-experiment series `results/diagnostics/cpu-pair-b-time-repro-120x2-20260929-escalated`.
- Outlier sensitivity: reuse the prior artifact's per-CPU method: exclude the largest run median once, and separately exclude the largest ceil(5%) run medians. This is supplementary sensitivity only; primary statistics use every successful run.
- Publication: `artifacts/cpu-pair-b-time-repro/summary-3x120.md`, `public-data-3x120.json`, and `run-observations-3x120.csv`. Local raw plans, runs, binaries, result JSON, logs, and monitor records stay under the ignored `results/diagnostics/` directory and will not be committed.
- No frequency, boost, thermal, or scheduler diagnostics are added in this change.

## Preflight limitation

Git HTTPS fetch/pull could not acquire Windows Git credentials (`SEC_E_NO_CREDENTIALS`). The GitHub API reported `origin/main` at the same SHA as local `main` and PR #56's merge commit, so there was no fast-forward to apply. The work branch was created from that verified commit.

The first invocation at 2026-09-29 09:19 JST created only an empty first-run directory and failed while GCC tried to create a temporary file under `%LOCALAPPDATA%\Temp` (`Permission denied`). It stopped before any benchmark run/sample. The manifest and error log are preserved at `results/diagnostics/cpu-pair-b-time-repro-3x120-20260929/`. The existing repeat runner gained an optional ID argument so the fixed group ID could be reused; the retry used a separate new path and workspace-local `%TEMP%`/`%TMP%`. Cycle count, experiment count, hardware pair, benchmark conditions, and analysis stayed fixed. All three retry experiments completed 240/240 runs; monitor coverage was 239/240, 237/240 and 239/240.
