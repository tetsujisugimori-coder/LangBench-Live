# 均衡順序測定

- series ID: `issue66-balanced-final-01`
- 測定Git SHA: `fde3f78b385034248bac9dfe7a97c8da37ffb3ae`

固定したD,F,F,D×3の12-run計画を完了しました。36言語run、各case 50 sample、合計3,600 samplesです。
数値はpublic-samples.csvから検算し、詳細はpublic-data.json / CSVに保存しています。

| 言語 | 順序群 | median delta (ms) | median ratio | positive | negative | zero |
|---|---|---:|---:|---:|---:|---:|
| Python | direct_first | +14.327000 | 1.742317 | 6 | 0 | 0 |
| Python | function_call_first | +13.382500 | 1.689876 | 6 | 0 | 0 |
| JavaScript | direct_first | -0.001750 | 0.995946 | 2 | 4 | 0 |
| JavaScript | function_call_first | +0.000500 | 1.001155 | 3 | 2 | 1 |
| C | direct_first | +0.293750 | 3.824519 | 6 | 0 | 0 |
| C | function_call_first | +0.296500 | 3.913403 | 6 | 0 | 0 |

- 差は各runのfunction_call median − direct median、ratioはfunction_call / directです。表は各順序群6 runの差・ratioの中央値と、丸め前の差のsign countsを示します。
- msとratioは表示直前だけ小数6桁へ丸め、JSON/CSVの内部値は丸めません。分母0のratioはnullです。
- D/F順序群は固定12-run計画の記述的比較です。3,600 samplesを独立3,600実験とは扱いません。順序群差を純粋なorder effectや因果効果とは呼びません。
- JavaScriptは差が非常に小さく符号も混在しています。Python/Cは両順序で同方向ですが、今回の固定条件・単一実機範囲の記述結果です。
