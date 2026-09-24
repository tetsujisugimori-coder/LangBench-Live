# C measurement order diagnostic

A = direct → function_call; B = function_call → direct. Each row is one run; 50 samples are repeated measurements within that run.
0.2 ms is a descriptive cutoff, not a decision threshold.

## A

| Run | Pair | Case | Median ms | First 25 ms | Last 25 ms | ≥0.2 ms |
|---:|---:|---|---:|---:|---:|---:|
| 1 | 1 | direct | 0.12 | 0.12 | 0.12 | 1/50 |
| 1 | 1 | function_call | 0.4375 | 0.442 | 0.431 | 50/50 |
| 4 | 2 | direct | 0.104 | 0.104 | 0.104 | 0/50 |
| 4 | 2 | function_call | 0.415 | 0.415 | 0.412 | 50/50 |
| 5 | 3 | direct | 0.113 | 0.114 | 0.105 | 0/50 |
| 5 | 3 | function_call | 0.418 | 0.408 | 0.418 | 50/50 |
| 8 | 4 | direct | 0.111 | 0.105 | 0.118 | 0/50 |
| 8 | 4 | function_call | 0.4365 | 0.436 | 0.439 | 50/50 |
| 9 | 5 | direct | 0.113 | 0.113 | 0.113 | 0/50 |
| 9 | 5 | function_call | 0.4435 | 0.445 | 0.443 | 50/50 |
| 12 | 6 | direct | 0.1125 | 0.119 | 0.112 | 0/50 |
| 12 | 6 | function_call | 0.4225 | 0.424 | 0.422 | 50/50 |
| 13 | 7 | direct | 0.11 | 0.112 | 0.104 | 0/50 |
| 13 | 7 | function_call | 0.412 | 0.418 | 0.4 | 50/50 |
| 16 | 8 | direct | 0.105 | 0.107 | 0.105 | 0/50 |
| 16 | 8 | function_call | 0.4185 | 0.441 | 0.408 | 50/50 |
| 17 | 9 | direct | 0.104 | 0.104 | 0.104 | 0/50 |
| 17 | 9 | function_call | 0.418 | 0.419 | 0.412 | 50/50 |
| 20 | 10 | direct | 0.104 | 0.105 | 0.097 | 0/50 |
| 20 | 10 | function_call | 0.418 | 0.418 | 0.42 | 50/50 |

## B

| Run | Pair | Case | Median ms | First 25 ms | Last 25 ms | ≥0.2 ms |
|---:|---:|---|---:|---:|---:|---:|
| 2 | 1 | direct | 0.108 | 0.096 | 0.115 | 0/50 |
| 2 | 1 | function_call | 0.3935 | 0.405 | 0.386 | 50/50 |
| 3 | 2 | direct | 0.096 | 0.104 | 0.096 | 0/50 |
| 3 | 2 | function_call | 0.419 | 0.425 | 0.392 | 50/50 |
| 6 | 3 | direct | 0.1055 | 0.103 | 0.11 | 0/50 |
| 6 | 3 | function_call | 0.419 | 0.419 | 0.418 | 50/50 |
| 7 | 4 | direct | 0.107 | 0.113 | 0.103 | 0/50 |
| 7 | 4 | function_call | 0.4205 | 0.418 | 0.428 | 50/50 |
| 10 | 5 | direct | 0.1205 | 0.124 | 0.119 | 3/50 |
| 10 | 5 | function_call | 0.424 | 0.435 | 0.421 | 50/50 |
| 11 | 6 | direct | 0.111 | 0.104 | 0.113 | 0/50 |
| 11 | 6 | function_call | 0.418 | 0.418 | 0.418 | 50/50 |
| 14 | 7 | direct | 0.1075 | 0.104 | 0.116 | 0/50 |
| 14 | 7 | function_call | 0.418 | 0.41 | 0.418 | 50/50 |
| 15 | 8 | direct | 0.106 | 0.105 | 0.109 | 3/50 |
| 15 | 8 | function_call | 0.4205 | 0.422 | 0.42 | 50/50 |
| 18 | 9 | direct | 0.109 | 0.109 | 0.109 | 1/50 |
| 18 | 9 | function_call | 0.4185 | 0.419 | 0.418 | 50/50 |
| 19 | 10 | direct | 0.102 | 0.105 | 0.099 | 0/50 |
| 19 | 10 | function_call | 0.4325 | 0.453 | 0.423 | 50/50 |
