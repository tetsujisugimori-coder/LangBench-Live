# C/direct CPU affinity: 40-cycle, 120-run diagnosis

All values are recalculated from this file's run-level medians and 50 raw samples per successful run.
Standard deviation is the population standard deviation of successful run medians. Samples within a run are not treated as independent runs.
The 0.2 ms threshold is descriptive only and does not imply a cause or statistical significance.

## Conditions

| Condition | Planned | Success | Failed | Pending | Median of run medians (ms) | Mean (ms) | Population SD (ms) | Min (ms) | Max (ms) | Samples | ≥0.2 ms samples | Runs with ≥0.2 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| normal | 40 | 40 | 0 | 0 | 0.104 | 0.1161 | 0.031933759565701 | 0.096 | 0.2545 | 2000 | 90 | 6 |
| CPU A | 40 | 40 | 0 | 0 | 0.13475 | 0.1354375 | 0.026172549431608686 | 0.101 | 0.203 | 2000 | 159 | 12 |
| CPU B | 40 | 40 | 0 | 0 | 0.11725 | 0.12763750000000001 | 0.022882031023272388 | 0.101 | 0.182 | 2000 | 187 | 20 |

## Position × condition

| Position | Condition | Planned | Success | Failed | Pending | Median (ms) | Mean (ms) | Population SD (ms) | Min (ms) | Max (ms) | Samples | ≥0.2 ms samples | Runs with ≥0.2 ms |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | normal | 14 | 14 | 0 | 0 | 0.1035 | 0.10639285714285714 | 0.006959522180408068 | 0.096 | 0.1255 | 700 | 4 | 1 |
| 1 | CPU A | 13 | 13 | 0 | 0 | 0.139 | 0.13607692307692307 | 0.0291764170797147 | 0.101 | 0.203 | 650 | 45 | 4 |
| 1 | CPU B | 13 | 13 | 0 | 0 | 0.116 | 0.12584615384615386 | 0.019825570721617822 | 0.108 | 0.182 | 650 | 63 | 6 |
| 2 | normal | 13 | 13 | 0 | 0 | 0.104 | 0.11942307692307692 | 0.03514357702222641 | 0.096 | 0.229 | 650 | 36 | 2 |
| 2 | CPU A | 14 | 14 | 0 | 0 | 0.13875 | 0.14260714285714285 | 0.02230004690211962 | 0.111 | 0.181 | 700 | 69 | 4 |
| 2 | CPU B | 13 | 13 | 0 | 0 | 0.1215 | 0.1281923076923077 | 0.024717277094822732 | 0.101 | 0.182 | 650 | 53 | 7 |
| 3 | normal | 13 | 13 | 0 | 0 | 0.1055 | 0.12323076923076923 | 0.04107479827405654 | 0.096 | 0.2545 | 650 | 50 | 3 |
| 3 | CPU A | 13 | 13 | 0 | 0 | 0.1195 | 0.1270769230769231 | 0.02439723041804143 | 0.102 | 0.1805 | 650 | 45 | 4 |
| 3 | CPU B | 14 | 14 | 0 | 0 | 0.11725 | 0.12878571428571428 | 0.023645230782876923 | 0.105 | 0.171 | 700 | 71 | 7 |

## Provenance

- Experiment: `20260924_201136_function_call_numeric_sum`
- Binary SHA-256: `533274b673b6892ba2c57051b89da1d4352fb04cffdff8bad211d297568a0184`
- C source SHA-256: `b107c19cdcc972e23c5968cc217f7c9ec88b06b840ab5aac8daa888fbe16cad3`
- Raw plan: `plan.json` SHA-256 `bb8742455926dfdaea05ee825a99bc02ca267f0eeaeb6578169af8056fffa0b9`
- Raw runs: `runs.json` SHA-256 `fc36ae48c9fb33b46b7095318450b3cc93b66ed166669541ebfcf75ea4fc95d2`
- Raw optimization_analysis: `optimization-analysis.json` SHA-256 `171ab2154e38fe1ee32dc3feaab5f8db6500d01b2ce7ca8aca77d6147dc57727`
- Each successful run includes the SHA-256 and filename of its source result JSON.
