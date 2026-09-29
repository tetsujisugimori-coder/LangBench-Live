# CPU B elapsed-time independent repeats (2026-09-29)

## Fixed plan and data boundaries

PR #56 was merged; main SHA was `f72c582e274e928ac3f19b4ca9417de0a3327dfe`. The three new experiments share `repeat-20260929_091948-2ad7b1ff`; each is analyzed independently, without joining elapsed timelines.

Conditions: group 0 CPU A=0 / B=1, same-core siblings; C/direct `function_call_numeric_sum`; 1,000,000 inputs; 5 warmups; 50 samples per run; direct then function_call; GCC 16.1.0, `-O2 -std=c11 -Wall -Wextra`; balanced ABBA, 120 cycles per new experiment. Each invocation recompiles; binary SHA-256 values are recorded and differ. C source SHA-256 and compiler/measurement settings match.

The first runner invocation failed before measurement because GCC could not create a temp file under the default Windows Temp ACL. Its empty output directory and log remain in `results/diagnostics/cpu-pair-b-time-repro-3x120-20260929/`. The successful rerun used a workspace-local TEMP/TMP and retained the same repeat ID. No sample data came from the failed attempt.

Local raw data (runs, all 50 samples, per-run result JSON, plans, binaries, logs, monitor JSON and QPC metadata) are under `results/diagnostics/cpu-pair-b-time-repro-3x120-20260929-retry/` and remain ignored/uncommitted. The public files omit raw samples, full monitor series, local paths, executables and logs. The CSV publishes one row per successful run, including timestamps, median, elapsed offset and available QPC-overlap system-wide busy median.

## Per-experiment results

Elapsed r uses each run's start offset from its own experiment start. Early and late are the first and last halves of complete cycles. Values are run-median medians in ms.

| Experiment ID | cycles | success / planned | duration (s) | A r | A early → late (Δ ms) | B r | B early → late (Δ ms) | busy covered / successful |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20260928_054539_function_call_numeric_sum | 30 | 60/60 | 13.456 | +0.007 | 0.1050 → 0.1050 (+0.0000) | +0.460 | 0.1050 → 0.1135 (+0.0085) | 59/60 |
| 20260928_063153_function_call_numeric_sum | 120 | 240/240 | 65.726 | +0.098 | 0.1070 → 0.1110 (+0.0040) | -0.127 | 0.1110 → 0.1110 (+0.0000) | 239/240 |
| 20260929_033048_function_call_numeric_sum | 120 | 240/240 | 76.709 | +0.018 | 0.1050 → 0.1055 (+0.0005) | +0.100 | 0.1050 → 0.1050 (+0.0000) | 238/240 |
| 20260929_033205_function_call_numeric_sum | 120 | 240/240 | 66.424 | +0.053 | 0.1050 → 0.1110 (+0.0060) | -0.061 | 0.1080 → 0.1110 (+0.0030) | 239/240 |
| 20260928_063125_function_call_numeric_sum | 30 | 60/60 | 13.979 | -0.086 | 0.1065 → 0.1050 (-0.0015) | +0.122 | 0.1050 → 0.1050 (+0.0000) | 59/60 |
| 20260929_092208_function_call_numeric_sum | 120 | 240/240 | 48.300 | -0.032 | 0.1110 → 0.1110 (+0.0000) | +0.061 | 0.1110 → 0.1110 (+0.0000) | 239/240 |
| 20260929_092257_function_call_numeric_sum | 120 | 240/240 | 46.822 | +0.049 | 0.1110 → 0.1110 (+0.0000) | -0.109 | 0.1110 → 0.1110 (+0.0000) | 237/240 |
| 20260929_092344_function_call_numeric_sum | 120 | 240/240 | 46.942 | +0.168 | 0.1060 → 0.1110 (+0.0050) | +0.051 | 0.1110 → 0.1080 (-0.0030) | 239/240 |

## New run order, position, outlier and busy summaries

Outlier sensitivity follows the prior artifact method: remove the highest single run median and separately remove exactly ceil(5%) run medians within each CPU/experiment, sorting by descending median then ascending run_id to resolve ties. These are sensitivity values only; primary summaries keep all successful runs.

| Experiment | CPU | Order-specific elapsed r (A→B / B→A) | Position median (first / second, ms) | Elapsed r excluding max / top 5% | Busy–median r (n) | Busy median early → late (%) |
|---|---|---|---|---|---:|---|
| 20260929_092208_function_call_numeric_sum | A | -0.061 / -0.008 | 0.1110 / 0.1110 | -0.057 / -0.087 | -0.005 (n=119) | 17.46 → 16.20 |
| 20260929_092208_function_call_numeric_sum | B | +0.054 / +0.073 | 0.1110 / 0.1100 | +0.034 / -0.073 | +0.066 (n=120) | 15.80 → 15.78 |
| 20260929_092257_function_call_numeric_sum | A | +0.105 / -0.007 | 0.1110 / 0.1085 | -0.010 / -0.111 | +0.050 (n=118) | 12.22 → 15.70 |
| 20260929_092257_function_call_numeric_sum | B | -0.036 / -0.158 | 0.1110 / 0.1052 | -0.064 / -0.071 | -0.246 (n=119) | 13.17 → 17.58 |
| 20260929_092344_function_call_numeric_sum | A | +0.089 / +0.259 | 0.1110 / 0.1050 | +0.148 / +0.126 | +0.121 (n=119) | 13.60 → 13.60 |
| 20260929_092344_function_call_numeric_sum | B | +0.157 / -0.004 | 0.1110 / 0.1050 | +0.000 / -0.021 | +0.115 (n=120) | 14.01 → 15.53 |

## Interpretation

The earlier large CPU B pattern (30-cycle r=+0.460 and late−early=+0.0085 ms) does not reproduce as a joint pattern across the three new 120-cycle experiments: only two of three new B correlations are positive, none has a positive late−early difference, and their magnitudes are small. The earlier 120-cycle group also varied in sign. These observations do not establish that small elapsed-time effects are absent; they show that the current runs do not decide that question. Busy-monitor associations vary and are descriptive, not causal.

Differences include cycle count (30 vs 120), independent start times, and separately compiled binary hashes. The C source SHA, CPU pair, compiler version, flags, benchmark configuration, direct/function_call order and ABBA schedule match for comparable runs. Frequency/boost/thermal/scheduler diagnostics are not added; another independent repeat remains the next candidate if small effects need resolution.

## Verification

The existing comparison tool validated and analyzed 8 distinct experiment IDs separately. The published CSV contains 1560 successful run rows. CPU A/B elapsed Pearson r, early/late medians, order/position medians and correlations, max/top-five-percent exclusion sensitivities, and busy–median correlations were recalculated from the CSV and matched public JSON within 1e-12. For top-five-percent sensitivity, ties use ascending run_id after descending median; exactly ceil(5%) rows are removed. For top-five-percent sensitivity, ties use ascending run_id after descending median; exactly ceil(5%) rows are removed.
