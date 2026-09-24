# C measurement order follow-up: 40 planned runs

A = direct → function_call; B = function_call → direct. Each run has 50 repeated samples per case.
0.2 ms is descriptive only; it is not a significance threshold. CPU averages cover roughly 20 ms and cannot identify the load or cause of an individual 0.1–0.3 ms sample.

## Planned conditions and direct distribution

| Order | Monitor | Planned | C success | Trace success | Monitor success | Direct run medians ms (sorted) | Slow runs | Slow samples |
|---|---|---:|---:|---:|---:|---|---:|---:|
| A | あり | 10 | 10 | 10 | 10 | 0.1025, 0.104, 0.104, 0.104, 0.104, 0.104, 0.104, 0.104, 0.105, 0.1525 | 0 | 0 |
| A | なし | 10 | 10 | 10 | 0 | 0.096, 0.104, 0.104, 0.104, 0.104, 0.104, 0.104, 0.104, 0.104, 0.104 | 2 | 2 |
| B | あり | 10 | 10 | 10 | 10 | 0.096, 0.096, 0.096, 0.096, 0.097, 0.102, 0.104, 0.104, 0.104, 0.115 | 1 | 2 |
| B | なし | 10 | 10 | 10 | 0 | 0.096, 0.096, 0.0985, 0.1015, 0.102, 0.104, 0.104, 0.104, 0.105, 0.113 | 0 | 0 |

## Every planned run

| Run | Pair/position | Order | Monitor | C | Trace | Monitor result | Direct median ms | ≥0.2 ms positions | Direct missing CPU samples |
|---:|---|---|---|---|---|---|---:|---|---:|
| 1 | 1/1 | A | あり | success | success | 取得成功 | 0.1025 | — | 50 |
| 2 | 1/2 | B | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |
| 3 | 2/1 | B | なし | success | success | CPU観測なし | 0.113 | — | CPU観測なし |
| 4 | 2/2 | A | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 5 | 3/1 | A | なし | success | success | CPU観測なし | 0.104 | 49 | CPU観測なし |
| 6 | 3/2 | B | あり | success | success | 取得成功 | 0.097 | — | 0 |
| 7 | 4/1 | B | あり | success | success | 取得成功 | 0.102 | — | 0 |
| 8 | 4/2 | A | なし | success | success | CPU観測なし | 0.096 | — | CPU観測なし |
| 9 | 5/1 | A | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 10 | 5/2 | B | なし | success | success | CPU観測なし | 0.102 | — | CPU観測なし |
| 11 | 6/1 | B | なし | success | success | CPU観測なし | 0.096 | — | CPU観測なし |
| 12 | 6/2 | A | あり | success | success | 取得成功 | 0.1525 | — | 0 |
| 13 | 7/1 | A | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |
| 14 | 7/2 | B | あり | success | success | 取得成功 | 0.096 | — | 0 |
| 15 | 8/1 | B | あり | success | success | 取得成功 | 0.096 | — | 0 |
| 16 | 8/2 | A | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |
| 17 | 9/1 | A | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 18 | 9/2 | B | なし | success | success | CPU観測なし | 0.1015 | — | CPU観測なし |
| 19 | 10/1 | B | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |
| 20 | 10/2 | A | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 21 | 11/1 | A | なし | success | success | CPU観測なし | 0.104 | 8 | CPU観測なし |
| 22 | 11/2 | B | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 23 | 12/1 | B | あり | success | success | 取得成功 | 0.115 | 1, 42 | 0 |
| 24 | 12/2 | A | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |
| 25 | 13/1 | A | あり | success | success | 取得成功 | 0.105 | — | 0 |
| 26 | 13/2 | B | なし | success | success | CPU観測なし | 0.105 | — | CPU観測なし |
| 27 | 14/1 | B | なし | success | success | CPU観測なし | 0.0985 | — | CPU観測なし |
| 28 | 14/2 | A | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 29 | 15/1 | A | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |
| 30 | 15/2 | B | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 31 | 16/1 | B | あり | success | success | 取得成功 | 0.096 | — | 0 |
| 32 | 16/2 | A | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |
| 33 | 17/1 | A | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 34 | 17/2 | B | なし | success | success | CPU観測なし | 0.096 | — | CPU観測なし |
| 35 | 18/1 | B | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |
| 36 | 18/2 | A | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 37 | 19/1 | A | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |
| 38 | 19/2 | B | あり | success | success | 取得成功 | 0.104 | — | 0 |
| 39 | 20/1 | B | あり | success | success | 取得成功 | 0.096 | — | 0 |
| 40 | 20/2 | A | なし | success | success | CPU観測なし | 0.104 | — | CPU観測なし |

## Slow direct samples and QPC overlap

Overlaps compare raw QPC intervals. A missing CPU value is not zero load. No overlap does not rule out a short load change.

| Run | Sample | ms | Sample QPC interval | Overlapping monitor interval QPC |
|---:|---:|---:|---|---|
| 5 | 49 | 0.214 | 2362181090628–2362181092768 | CPU観測なし |
| 21 | 8 | 0.21 | 2362805641623–2362805643724 | CPU観測なし |
| 23 | 1 | 0.208 | 2362885544230–2362885546313 | 97: 2362885502686–2362885705992 (CPU値あり) |
| 23 | 42 | 0.208 | 2362885593401–2362885595485 | 97: 2362885502686–2362885705992 (CPU値あり) |

観測区間の重なりは時間的な対応だけを示します。CPU負荷を遅延原因とは判定しません。
