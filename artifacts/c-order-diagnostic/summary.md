# C measurement order diagnostic

A = direct → function_call; B = function_call → direct. Each row is one run; 50 samples are repeated measurements within that run.
0.2 ms is a descriptive cutoff, not a decision threshold.

## A

| Run | Pair | Case | Median ms | First 25 ms | Last 25 ms | ≥0.2 ms |
|---:|---:|---|---:|---:|---:|---:|
| 1 | 1 | direct | 0.1155 | 0.116 | 0.114 | 12/50 |
| 1 | 1 | function_call | 0.4095 | 0.41 | 0.409 | 50/50 |
| 4 | 2 | direct | 0.104 | 0.104 | 0.104 | 0/50 |
| 4 | 2 | function_call | 0.386 | 0.386 | 0.389 | 50/50 |
| 5 | 3 | direct | 0.151 | 0.104 | 0.177 | 18/50 |
| 5 | 3 | function_call | 0.3915 | 0.418 | 0.39 | 50/50 |
| 8 | 4 | direct | 0.113 | 0.113 | 0.113 | 0/50 |
| 8 | 4 | function_call | 0.418 | 0.418 | 0.418 | 50/50 |
| 9 | 5 | direct | 0.113 | 0.113 | 0.113 | 0/50 |
| 9 | 5 | function_call | 0.4195 | 0.42 | 0.419 | 50/50 |
| 12 | 6 | direct | 0.113 | 0.112 | 0.117 | 1/50 |
| 12 | 6 | function_call | 0.4195 | 0.421 | 0.419 | 50/50 |
| 13 | 7 | direct | 0.126 | 0.126 | 0.12 | 0/50 |
| 13 | 7 | function_call | 0.464 | 0.479 | 0.442 | 50/50 |
| 16 | 8 | direct | 0.2445 | 0.298 | 0.204 | 38/50 |
| 16 | 8 | function_call | 0.386 | 0.391 | 0.386 | 50/50 |
| 17 | 9 | direct | 0.17 | 0.17 | 0.17 | 0/50 |
| 17 | 9 | function_call | 0.422 | 0.428 | 0.418 | 50/50 |
| 20 | 10 | direct | 0.104 | 0.104 | 0.104 | 0/50 |
| 20 | 10 | function_call | 0.386 | 0.386 | 0.386 | 50/50 |

## B

| Run | Pair | Case | Median ms | First 25 ms | Last 25 ms | ≥0.2 ms |
|---:|---:|---|---:|---:|---:|---:|
| 2 | 1 | direct | 0.104 | 0.104 | 0.108 | 0/50 |
| 2 | 1 | function_call | 0.386 | 0.386 | 0.386 | 50/50 |
| 3 | 2 | direct | 0.113 | 0.113 | 0.113 | 0/50 |
| 3 | 2 | function_call | 0.418 | 0.418 | 0.418 | 50/50 |
| 6 | 3 | direct | 0.0965 | 0.099 | 0.096 | 0/50 |
| 6 | 3 | function_call | 0.418 | 0.514 | 0.394 | 50/50 |
| 7 | 4 | direct | 0.105 | 0.105 | 0.104 | 0/50 |
| 7 | 4 | function_call | 0.418 | 0.418 | 0.418 | 50/50 |
| 10 | 5 | direct | 0.104 | 0.104 | 0.104 | 0/50 |
| 10 | 5 | function_call | 0.418 | 0.418 | 0.418 | 50/50 |
| 11 | 6 | direct | 0.112 | 0.112 | 0.112 | 0/50 |
| 11 | 6 | function_call | 0.4255 | 0.576 | 0.418 | 50/50 |
| 14 | 7 | direct | 0.105 | 0.107 | 0.105 | 0/50 |
| 14 | 7 | function_call | 0.423 | 0.422 | 0.423 | 50/50 |
| 15 | 8 | direct | 0.106 | 0.112 | 0.104 | 0/50 |
| 15 | 8 | function_call | 0.421 | 0.493 | 0.418 | 50/50 |
| 18 | 9 | direct | 0.113 | 0.113 | 0.113 | 0/50 |
| 18 | 9 | function_call | 0.421 | 0.43 | 0.418 | 50/50 |
| 19 | 10 | direct | 0.104 | 0.104 | 0.105 | 0/50 |
| 19 | 10 | function_call | 0.3875 | 0.39 | 0.386 | 50/50 |
