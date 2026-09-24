# C measurement order follow-up: 40 planned runs

A = direct → function_call; B = function_call → direct. Each run has 50 repeated samples per case.
0.2 ms is descriptive only; it is not a significance threshold. CPU averages cover roughly 20 ms and cannot identify the load or cause of an individual 0.1–0.3 ms sample.

## Planned conditions and direct distribution

| Order | Monitor | Planned | C success | Trace success | Monitor success | Direct run medians ms (sorted) | Slow runs | Slow samples |
|---|---|---:|---:|---:|---:|---|---:|---:|
| A | あり | 10 | 0 | 0 | 10 | — | 0 | 0 |
| A | なし | 10 | 0 | 0 | 0 | — | 0 | 0 |
| B | あり | 10 | 0 | 0 | 10 | — | 0 | 0 |
| B | なし | 10 | 0 | 0 | 0 | — | 0 | 0 |

## Every planned run

| Run | Pair/position | Order | Monitor | C | Trace | Monitor result | Direct median ms | ≥0.2 ms positions | Direct missing CPU samples |
|---:|---|---|---|---|---|---|---:|---|---:|
| 1 | 1/1 | A | あり | failed | failed | 取得成功 | — | — | — |
| 2 | 1/2 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 3 | 2/1 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 4 | 2/2 | A | あり | failed | failed | 取得成功 | — | — | — |
| 5 | 3/1 | A | なし | failed | failed | CPU観測なし | — | — | — |
| 6 | 3/2 | B | あり | failed | failed | 取得成功 | — | — | — |
| 7 | 4/1 | B | あり | failed | failed | 取得成功 | — | — | — |
| 8 | 4/2 | A | なし | failed | failed | CPU観測なし | — | — | — |
| 9 | 5/1 | A | あり | failed | failed | 取得成功 | — | — | — |
| 10 | 5/2 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 11 | 6/1 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 12 | 6/2 | A | あり | failed | failed | 取得成功 | — | — | — |
| 13 | 7/1 | A | なし | failed | failed | CPU観測なし | — | — | — |
| 14 | 7/2 | B | あり | failed | failed | 取得成功 | — | — | — |
| 15 | 8/1 | B | あり | failed | failed | 取得成功 | — | — | — |
| 16 | 8/2 | A | なし | failed | failed | CPU観測なし | — | — | — |
| 17 | 9/1 | A | あり | failed | failed | 取得成功 | — | — | — |
| 18 | 9/2 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 19 | 10/1 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 20 | 10/2 | A | あり | failed | failed | 取得成功 | — | — | — |
| 21 | 11/1 | A | なし | failed | failed | CPU観測なし | — | — | — |
| 22 | 11/2 | B | あり | failed | failed | 取得成功 | — | — | — |
| 23 | 12/1 | B | あり | failed | failed | 取得成功 | — | — | — |
| 24 | 12/2 | A | なし | failed | failed | CPU観測なし | — | — | — |
| 25 | 13/1 | A | あり | failed | failed | 取得成功 | — | — | — |
| 26 | 13/2 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 27 | 14/1 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 28 | 14/2 | A | あり | failed | failed | 取得成功 | — | — | — |
| 29 | 15/1 | A | なし | failed | failed | CPU観測なし | — | — | — |
| 30 | 15/2 | B | あり | failed | failed | 取得成功 | — | — | — |
| 31 | 16/1 | B | あり | failed | failed | 取得成功 | — | — | — |
| 32 | 16/2 | A | なし | failed | failed | CPU観測なし | — | — | — |
| 33 | 17/1 | A | あり | failed | failed | 取得成功 | — | — | — |
| 34 | 17/2 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 35 | 18/1 | B | なし | failed | failed | CPU観測なし | — | — | — |
| 36 | 18/2 | A | あり | failed | failed | 取得成功 | — | — | — |
| 37 | 19/1 | A | なし | failed | failed | CPU観測なし | — | — | — |
| 38 | 19/2 | B | あり | failed | failed | 取得成功 | — | — | — |
| 39 | 20/1 | B | あり | failed | failed | 取得成功 | — | — | — |
| 40 | 20/2 | A | なし | failed | failed | CPU観測なし | — | — | — |

## Slow direct samples and QPC overlap

Overlaps compare raw QPC intervals. A missing CPU value is not zero load. No overlap does not rule out a short load change.

| Run | Sample | ms | Sample QPC interval | Overlapping monitor interval QPC |
|---:|---:|---:|---|---|
| — | — | — | — | No ≥0.2 ms direct samples |

監視ありの遅いdirectサンプルは0件です。CPU負荷との関係は判定不能です。

観測区間の重なりは時間的な対応だけを示します。CPU負荷を遅延原因とは判定しません。
