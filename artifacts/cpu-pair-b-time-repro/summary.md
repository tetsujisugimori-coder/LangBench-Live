# CPU B 時間依存傾向の独立反復（2026-09-29）

## 測定条件と保存先

PR #54 マージ済みの `main`（`87409d5313a8d646a2159e8ccd60a718c2acc974`）から作業を開始した。既存の `tools/repeat_cpu_pair.py` で `same_core_siblings` を 120 cycle × 2 独立実験として測定した。`repeat_experiment_id` は `repeat-20260929_033047-7549188e`、各 `experiment_id` は下表に示す。1 cycle は CPU A と B の各 1 run。CPU A は group 0 / logical CPU 0、CPU B は group 0 / logical CPU 1（同じ physical core、raw EfficiencyClass 1）。

測定は `function_call_numeric_sum` の C/direct、入力 1,000,000、warmup 5 回、direct/function_call 各 50 回、`-O2 -std=c11 -Wall -Wextra`、affinity 指定を使用した。ABBA ブロックにより各 120 cycle の A→B / B→A は 60 / 60、前半 60 cycle と後半 60 cycle の各半でも 30 / 30。system-wide CPU busy は既存の Windows CPU monitor と QPC overlap による run 単位の中央値で取得した。既存の early / late 定義（complete cycle の前半・後半）、elapsed と run median の Pearson 相関、order / position 分析をそのまま使用した。

旧 30-cycle 実験と旧 120-cycle 実験は同じ C source SHA-256、測定設定（cycle 数を除く）、CPU pair metadata、compiler version、環境を持つ。cycle 数だけが 30 対 120 で異なり、観測時間と相関の安定性に影響し得る。各独立実験で C を再コンパイルする既存 CLI のため、binary SHA-256 は 4 実験間で異なる。bitwise 同一バイナリを使った比較とは主張しない。値と各 SHA-256 は `public-data.json` に保存した。

新規の生データは `results/diagnostics/cpu-pair-b-time-repro-120x2-20260929-escalated/` に保存した（リポジトリの既存 `.gitignore` 対象）。`manifest.json`、各実験の `plan.json` / `runs.json` / run JSON / CPU monitor JSON、および `comparison.json` と `compare-prior.json` がある。この PR の `public-data.json` は旧実験を含む既存分析結果と追加の感度確認を抜粋し、`run-observations.csv` は run 単位の `run_id`、cycle、started_at、CPU、order、position、elapsed、median_ms、system-wide busy を保存した。生の 50 samples と CPU monitor の全観測値はローカルの生データに残した。

最初の通常権限での試行は gcc が一時ファイルを作成できず、測定前に終了した。この失敗記録は `results/diagnostics/cpu-pair-b-time-repro-120x2-20260929/` に分離し、今回の観測には含めていない。

## 旧実験との比較

各実験を独立に解析し、elapsed 系列を連結していない。相関の説明変数は実験開始から各 run 開始までの秒数。early / late は run median の中央値（ms）。

| 実験（開始日時） | cycle / CPU | A elapsed r | A early → late / 差 (ms) | B elapsed r | B early → late / 差 (ms) |
|---|---:|---:|---:|---:|---:|
| 旧・正傾向 `20260928_054539` | 30 | +0.007 | 0.105 → 0.105 / 0 | +0.460 | 0.105 → 0.1135 / +0.0085 |
| 旧・独立長時間 `20260928_063153` | 120 | +0.098 | 0.107 → 0.111 / +0.004 | −0.127 | 0.111 → 0.111 / 0 |
| 新 run 1 `20260929_033048` | 120 | +0.018 | 0.105 → 0.1055 / +0.0005 | +0.100 | 0.105 → 0.105 / 0 |
| 新 run 2 `20260929_033205` | 120 | +0.053 | 0.105 → 0.111 / +0.006 | −0.061 | 0.108 → 0.111 / +0.003 |

全 run 成功。新 run の elapsed 相関は各 CPU 120 点、busy coverage は run 1 が 238/240（complete pair 118/120）、run 2 が 239/240（119/120）。旧 30-cycle は 59/60（29/30）、旧 120-cycle は 239/240（119/120）。busy 欠損 run は相関計算から除外した。

## 分布と外れ値

新 run 1 の B run median は Q1/中央値/Q3 が 0.101/0.105/0.111 ms、最大 0.3875 ms。新 run 2 は 0.101/0.111/0.111 ms、最大 0.4965 ms。旧正傾向の B は 0.1045/0.111/0.116 ms、最大 0.147 ms。外れ値を見ずに Pearson r だけを比較するのは適切でない。

B の最大 run median 1 点を除く elapsed r は、旧正傾向 +0.361、新 run 1 +0.055、新 run 2 −0.058。上位 5% の run median を除くと順に +0.322、−0.037、+0.241。特に新 run 2 は除外方法で符号が変わる。これらは事後の感度確認であり、元の相関や early / late 差を置き換えない。

## order / position

ABBA では A→B 時に A が first / B が second、B→A 時に B が first / A が second となる。このため CPU 内の order 別と position 別は同じ run 分割だが、両方のラベルで `public-data.json` と `run-observations.csv` に保存した。

| 実験 | CPU | A→B の elapsed r (n) | B→A の elapsed r (n) | first / second median (ms) |
|---|---|---:|---:|---:|
| 旧・正傾向 | A | +0.132 (15) | −0.051 (15) | 0.105 / 0.103 |
| 旧・正傾向 | B | +0.399 (15) | +0.530 (15) | 0.111 / 0.111 |
| 旧・独立長時間 | A | +0.008 (60) | +0.185 (60) | 0.111 / 0.10825 |
| 旧・独立長時間 | B | −0.161 (60) | −0.094 (60) | 0.111 / 0.111 |
| 新 run 1 | A | −0.159 (60) | +0.071 (60) | 0.10875 / 0.105 |
| 新 run 1 | B | +0.130 (60) | +0.114 (60) | 0.1055 / 0.105 |
| 新 run 2 | A | +0.252 (60) | −0.009 (60) | 0.11025 / 0.109 |
| 新 run 2 | B | +0.321 (60) | −0.115 (60) | 0.111 / 0.108 |

旧正傾向は B の両順序で正。新 run 1 も両順序で弱い正だが、early / late 差は 0。新 run 2 は順序・位置で符号が割れ、全体の相関も負。各半の順序・位置回数は均衡しており、単純な回数偏りだけで旧傾向や今回の不一致を説明できない。一方、順序別の関連は変動しており、交絡や外れ値の影響を排除したとは言えない。

## system-wide CPU busy

| 実験 | A busy–median r (n) | B busy–median r (n) | B busy 中央値 early → late (%) |
|---|---:|---:|---:|
| 旧・正傾向 | +0.159 (29) | −0.235 (30) | 27.68 → 26.82 |
| 旧・独立長時間 | +0.037 (120) | −0.064 (119) | 13.33 → 12.25 |
| 新 run 1 | +0.229 (120) | +0.271 (118) | 14.29 → 13.73 |
| 新 run 2 | +0.035 (120) | +0.286 (119) | 13.85 → 14.29 |

新 run 1 の B busy は後半に上昇せず、B の early / late 差も 0。新 run 2 では B busy がわずかに上昇し、busy と B median に弱い正の関連があるが、B elapsed r は負。system-wide busy の上昇のみで旧 B 時間傾向を説明できるという一貫した対応は見られない。run 単位の busy 観測には欠損があり、因果関係は示さない。

## 判断と検証

新しい 2 回の独立 120-cycle 実験では、旧 30-cycle 実験の B に見られた正の elapsed r と大きな正の late−early 差が同時には観測されなかった。既存の別の 120-cycle 実験も B r が負、late−early が 0。今回のデータでは「再現傾向あり」とは言えず、旧 30-cycle の観測はその実験固有の揺らぎだった可能性がある。小さい効果の有無を確定したわけではない。次に確認するなら同条件の追加独立反復を優先し、frequency / boost / thermal / scheduler 診断の追加は現時点で根拠が弱い。

検証は `python -B -m unittest discover -s tests -q`（158 件成功）、`node --test tests/test_javascript_optimization_analysis.js`（22 件成功）、PowerShell の C OS version 5 件、measurement order 2 件、optimization analysis 16 件を実行した。既存比較器で旧 2 実験と新 2 実験を同時に読み、旧データ読み込み、異なる `experiment_id` / `repeat_experiment_id`、前半・後半の従来定義、order / position 集計を確認した。測定値を固定値とするテストは追加していない。
