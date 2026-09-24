# C measurement order diagnostic

A = direct → function_call; B = function_call → direct. Each row is one run; 50 samples are repeated measurements within that run.
0.2 ms is a descriptive cutoff, not a decision threshold.

## A

| Run | Pair | Case | Median ms | First 25 ms | Last 25 ms | ≥0.2 ms |
|---:|---:|---|---:|---:|---:|---:|
| 1 | 1 | direct | 0.1125 | 0.105 | 0.117 | 0/50 |
| 1 | 1 | function_call | 0.421 | 0.422 | 0.418 | 50/50 |
| 4 | 2 | direct | 0.104 | 0.106 | 0.103 | 0/50 |
| 4 | 2 | function_call | 0.3895 | 0.39 | 0.389 | 50/50 |
| 5 | 3 | direct | 0.149 | 0.276 | 0.113 | 13/50 |
| 5 | 3 | function_call | 0.418 | 0.418 | 0.418 | 50/50 |
| 8 | 4 | direct | 0.0995 | 0.104 | 0.097 | 0/50 |
| 8 | 4 | function_call | 0.406 | 0.401 | 0.412 | 50/50 |
| 9 | 5 | direct | 0.1085 | 0.111 | 0.104 | 0/50 |
| 9 | 5 | function_call | 0.406 | 0.411 | 0.403 | 50/50 |
| 12 | 6 | direct | 0.108 | 0.112 | 0.104 | 0/50 |
| 12 | 6 | function_call | 0.389 | 0.386 | 0.393 | 50/50 |
| 13 | 7 | direct | 0.112 | 0.112 | 0.113 | 5/50 |
| 13 | 7 | function_call | 0.418 | 0.418 | 0.418 | 50/50 |
| 16 | 8 | direct | 0.111 | 0.118 | 0.106 | 0/50 |
| 16 | 8 | function_call | 0.4185 | 0.419 | 0.418 | 50/50 |
| 17 | 9 | direct | 0.1205 | 0.119 | 0.123 | 0/50 |
| 17 | 9 | function_call | 0.42 | 0.422 | 0.419 | 50/50 |
| 20 | 10 | direct | 0.1055 | 0.124 | 0.104 | 0/50 |
| 20 | 10 | function_call | 0.4225 | 0.421 | 0.424 | 50/50 |

## B

| Run | Pair | Case | Median ms | First 25 ms | Last 25 ms | ≥0.2 ms |
|---:|---:|---|---:|---:|---:|---:|
| 2 | 1 | direct | 0.112 | 0.112 | 0.113 | 0/50 |
| 2 | 1 | function_call | 0.418 | 0.41 | 0.42 | 50/50 |
| 3 | 2 | direct | 0.106 | 0.113 | 0.103 | 0/50 |
| 3 | 2 | function_call | 0.3975 | 0.418 | 0.391 | 50/50 |
| 6 | 3 | direct | 0.096 | 0.096 | 0.103 | 0/50 |
| 6 | 3 | function_call | 0.4005 | 0.403 | 0.4 | 50/50 |
| 7 | 4 | direct | 0.104 | 0.104 | 0.104 | 0/50 |
| 7 | 4 | function_call | 0.403 | 0.415 | 0.397 | 50/50 |
| 10 | 5 | direct | 0.104 | 0.105 | 0.104 | 0/50 |
| 10 | 5 | function_call | 0.4185 | 0.421 | 0.414 | 50/50 |
| 11 | 6 | direct | 0.104 | 0.104 | 0.104 | 0/50 |
| 11 | 6 | function_call | 0.4085 | 0.407 | 0.41 | 50/50 |
| 14 | 7 | direct | 0.109 | 0.103 | 0.112 | 0/50 |
| 14 | 7 | function_call | 0.389 | 0.395 | 0.386 | 50/50 |
| 15 | 8 | direct | 0.104 | 0.107 | 0.104 | 0/50 |
| 15 | 8 | function_call | 0.418 | 0.418 | 0.396 | 50/50 |
| 18 | 9 | direct | 0.112 | 0.116 | 0.107 | 0/50 |
| 18 | 9 | function_call | 0.4345 | 0.422 | 0.461 | 50/50 |
| 19 | 10 | direct | 0.106 | 0.114 | 0.105 | 0/50 |
| 19 | 10 | function_call | 0.422 | 0.425 | 0.418 | 50/50 |

## Monitoring and temporal coverage

CPU busy is sampled over intervals using GetSystemTimes. C and monitor QPC ticks share the Windows performance counter; UTC labels use the C FILETIME anchor and are approximate. Overlap uses QPC ticks only.
Changes shorter than the requested 20 ms sampling interval can be missed. Missing CPU data does not mean zero load. Observations are temporal associations, not evidence of cause.

| Run | Order | Position | Monitor | Status | CPU valid/all | Interval median/max ms | Probe median/max ms | Direct median ms | Direct ≥0.2 ms | Direct case valid overlaps | Slow direct samples with valid overlap |
|---:|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | A | 1 | on | recorded | 152/155 | 20.7676/25.8125 | 0.1719/4.5982 | 0.1125 | 0/50 | 2 | 0/0 |
| 2 | B | 2 | off | not_planned | 0/0 | — | — | 0.112 | 0/50 | 0 | 0/0 |
| 3 | B | 1 | off | not_planned | 0/0 | — | — | 0.106 | 0/50 | 0 | 0/0 |
| 4 | A | 2 | on | recorded | 101/110 | 20.7551/21.4826 | 0.2035/0.8809 | 0.104 | 0/50 | 1 | 0/0 |
| 5 | A | 1 | off | not_planned | 0/0 | — | — | 0.149 | 13/50 | 0 | 0/13 |
| 6 | B | 2 | on | recorded | 103/113 | 20.6203/22.0007 | 0.1994/1.115 | 0.096 | 0/50 | 2 | 0/0 |
| 7 | B | 1 | on | recorded | 106/112 | 20.7377/21.8596 | 0.2971/1.1305 | 0.104 | 0/50 | 1 | 0/0 |
| 8 | A | 2 | off | not_planned | 0/0 | — | — | 0.0995 | 0/50 | 0 | 0/0 |
| 9 | A | 1 | on | recorded | 120/124 | 20.6256/24.2498 | 0.1792/0.9401 | 0.1085 | 0/50 | 1 | 0/0 |
| 10 | B | 2 | off | not_planned | 0/0 | — | — | 0.104 | 0/50 | 0 | 0/0 |
| 11 | B | 1 | off | not_planned | 0/0 | — | — | 0.104 | 0/50 | 0 | 0/0 |
| 12 | A | 2 | on | recorded | 116/120 | 20.6699/21.484 | 0.1627/0.745 | 0.108 | 0/50 | 2 | 0/0 |
| 13 | A | 1 | off | not_planned | 0/0 | — | — | 0.112 | 5/50 | 0 | 0/5 |
| 14 | B | 2 | on | recorded | 112/119 | 20.6523/21.5449 | 0.1483/0.8236 | 0.109 | 0/50 | 2 | 0/0 |
| 15 | B | 1 | on | recorded | 114/121 | 20.6609/22.3622 | 0.1575/2.0228 | 0.104 | 0/50 | 1 | 0/0 |
| 16 | A | 2 | off | not_planned | 0/0 | — | — | 0.111 | 0/50 | 0 | 0/0 |
| 17 | A | 1 | on | recorded | 113/116 | 20.6456/21.6901 | 0.1889/0.7825 | 0.1205 | 0/50 | 2 | 0/0 |
| 18 | B | 2 | off | not_planned | 0/0 | — | — | 0.112 | 0/50 | 0 | 0/0 |
| 19 | B | 1 | on | recorded | 106/112 | 20.6199/22.4904 | 0.1896/0.7378 | 0.106 | 0/50 | 2 | 0/0 |
| 20 | A | 2 | off | not_planned | 0/0 | — | — | 0.1055 | 0/50 | 0 | 0/0 |

## Direct distribution by planned condition

| Order | Monitor | Successful runs | Median range ms | ≥0.2 ms samples / samples |
|---|---|---:|---:|---:|
| A | on | 5 | 0.104–0.1205 | 0/250 |
| A | off | 5 | 0.0995–0.149 | 18/250 |
| B | on | 5 | 0.096–0.109 | 0/250 |
| B | off | 5 | 0.104–0.112 | 0/250 |
