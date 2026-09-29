# direct／function_call 実測と最適化解析の対応

## 結果

2026-09-29、Windows x64の同一マシンで各言語3つの独立プロセス実験を実行した。各実験は1,000,000整数、warmup 5回、各ケース50 samples、direct→function_call順、期待checksum `500000500000`。表の平均・中央値・標本標準偏差はrun内50 samplesから再計算。実験間の差は各runの中央値から計算した。

| 言語 | 独立実験 | direct中央値 ms（各実験） | function_call中央値 ms（各実験） | 中央値差 call−direct ms（各実験） | 中央値差の実験間中央値・範囲 ms | 中央値比の実験間中央値・範囲 |
| --- | ---: | --- | --- | --- | --- | --- |
| C | 3 | 0.096 / 0.151 / 0.096 | 0.385 / 0.413 / 0.386 | +0.289 / +0.262 / +0.290 | +0.289 [0.262, 0.290] | 4.010 [2.735, 4.021] |
| Python | 3 | 18.920 / 19.284 / 20.065 | 32.306 / 32.816 / 32.551 | +13.386 / +13.532 / +12.486 | +13.386 [12.486, 13.532] | 1.702 [1.622, 1.708] |
| JavaScript | 3 | 0.472 / 0.472 / 0.431 | 0.486 / 0.491 / 0.429 | +0.014 / +0.019 / −0.002 | +0.014 [−0.002, 0.019] | 1.030 [0.995, 1.040] |

runごとのばらつきは標本標準偏差として公開CSVに記録した。run内50 samplesは独立実験50回ではない。JavaScriptでは中央値差の符号が3実験中1回負であり、3回の範囲にrun間変動がある。C/Pythonの今回の中央値差は3回すべて正だが、この小標本から効果の一般性や原因は判断しない。

## PR #60解析資料との対応

resultごとにソースSHA-256、処理系、アーキテクチャ、コンパイル／起動条件がPR #60 manifestと一致し、provenanceは全9件で `matched`。manifestと現行ソースSHAも再計算して一致を確認した。

- **C**: GCC 16.1.0、x64、`-O2 -std=c11 -Wall -Wextra`。対象 `function_call` の `add` はインライン化未検出。`direct_sum` はベクトル化とSSE2を検出。ここでの実測差は時間の対応を示すだけで、ベクトル化やSSE2が差を生じさせた証明ではない。
- **Python**: CPython 3.14.7、amd64、`optimize=0`。`function_call` のインライン化・ベクトル化は未検出、SIMDは未確認。資料はJITの実作動を判定していない。
- **JavaScript**: Node.js 24.20.0 / V8 13.6.233.17-node.53、x64、起動オプションなし。JITと対象 `add` のインライン化を検出。ベクトル化と機械語/SIMDは未確認。実測差は小さく、run中央値差は正負両方だった。

最適化の判定はPR #60資料のコンパイラレポート、アセンブリ、Pythonバイトコード、V8トレースに基づく。実測時間から最適化の有無を推定していない。時間差と所見の併記から因果関係を主張しない。

## 再現性・データ境界

`public-data.json` と `public-data.csv` は独立実験単位の集約値、実行条件、所見、元JSONのSHA-256を公開する。50個のsample値は公開ファイルに含めない。生JSON、計時sample、staging内の生成物はignored `results/diagnostics/issue61-direct-function-call-20260929/results/raw-matched/` に置き、commitしない。公開集計はraw JSONから `tools/analyze_direct_function_call_comparison.py` で再計算できる。

既存の未追跡結果は主分析に混ぜず保持した。旧C/Python結果はソースSHAが現manifestと不一致、既存JavaScript結果はベンチマーク起動条件に解析用trace flagを含み不一致のため除外した。

experiment IDは既存validatorの形式制約に合わせて事前指定したtimestamp形式ラベルで、実際の時刻ではない。実時刻はresult `created_at` と `run_id` を使用する。

## 限界と次の判断

3独立実験、1台、1 OS、固定direct-first順の記述統計である。信頼区間や言語間速度順位を今回の結論にしない。最適化の因果を調べるには、別途、最適化条件だけを変える制御された測定計画が必要。本PRでは追加条件変更を行わず、この結果を関連付け資料としてレビューに回す。

隔離環境で既存archiveツールの一時ファイル作成がOS access deniedとなったため、各runでschema検証後のJSONを独立rawフォルダーへ直ちに複写した。三言語のベンチマーク検証は各runで成功し、archiveの問題は測定値を上書きせずraw複写で回避した。
