# direct／function_call 均衡順序測定計画（Issue #66）

結果を見る前に、対象を `function_call_numeric_sum`、言語順を Python → JavaScript → C、入力を
1,000,000 整数、期待 checksum を `500000500000`、warmup を各 case 5 回、測定を各 case 50 回に固定する。
独立プロセス run は各言語 12 回で、順序は D, F, F, D を3ブロックとする。D は direct →
function_call、F は function_call → direct であり、各順序は6回である。全体は36言語 run、3,600
sampleだが、sampleを独立実験とは扱わない。

差は常に function_call 中央値 − direct 中央値、比は function_call 中央値 ÷ direct 中央値とする。
分母0の比は null。標本標準偏差を用い、符号は丸め前に分類する。JSON/CSVには計算精度を保ち、
説明表示だけ ms は小数6桁、比は小数6桁へ丸める。外れ値除外や結果を理由とする追加測定はしない。

Windows対象機で、OS、CPU、処理系、コンパイル／起動option、affinity、source SHA-256、Git SHAを
記録して実行する。途中更新・欠損・checksum不一致・順序不一致はseries全体を不完全として止め、
再試行は新しいseries IDで行う。Cloud/CIの値は本測定へ代用しない。

```powershell
pwsh -NoProfile -File tools/remeasure_function_call.ps1 -BalancedOrder
python -B tools/analyze_balanced_order.py results/diagnostics/balanced-order/<series-id>/runs.json artifacts/direct-function-call-balanced-order
```

公開前に `python -B tools/verify_balanced_order_public_data.py artifacts/direct-function-call-balanced-order`
を実行する。元rawのhashはraw非公開時に第三者が再計算できず、公開sampleからの集計検算とは異なる。
本PR時点ではWindows本測定未実施であり、fixtureやCloud測定結果は公開結果に含めない。
