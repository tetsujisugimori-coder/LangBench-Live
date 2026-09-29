# direct／function_call 比較計画

計画固定日: 2026-09-29（結果確認前）

## 条件と反復

- 対象: PR #60 merge 後の現行 `main` ソースSHAと `artifacts/function-call-analysis/manifest.json`。
- 処理系: manifestに記録されたWindows x64、GCC 16.1.0 / `-O2 -std=c11 -Wall -Wextra`、CPython 3.14.7 / optimize=0、Node.js 24.20.0 / V8 13.6.233.17-node.53。Nodeの起動オプションなし、`NODE_OPTIONS`なし。
- 共通設定: 1,000,000整数、warmup 5回、測定50 samples、directを先に実行してからfunction_call。checksumは500000500000。
- 独立反復: 3回の完全な別プロセス実行（各実行でC・Python・JavaScript各1回）。各言語n=3独立実験。各run内50 samplesを独立実験数として扱わない。
- 変更しないもの: benchmark source、測定コード、コンパイラフラグ、実行順序、設定。測定出力は隔離した ignored raw-data staging directory に保存し、既存の未追跡 `results/` ファイルを上書きしない。

## 分析方法

- 各言語・各独立実験についてdirect/function_callの50 samplesから再計算した平均、中央値、標本標準偏差、最小、最大を報告する。
- 各独立実験の差は中央値差（function_call − direct）と中央値比（function_call / direct）で記述する。
- 言語ごとに独立実験3個の中央値差・比の範囲と中央値を要約する。50 samplesを独立実験のようにプールしない。
- 各resultのmanifest provenanceがmatchedであること、ソースSHA・処理系・起動/compile条件、checksum、公開要約再計算を検証する。元JSONのSHA-256を公開データへ記録する。
- PR #60の解析資料は測定時間の説明変数や因果証明としない。確認した最適化所見と時間差を同じ言語・同じ条件ごとに並べるだけとし、因果、一般的速度、言語間順位を結論しない。

## 除外と限界

- 既存のJSONはソースSHAまたはNode起動オプションが現manifestと一致しないため主分析から除外する。
- 失敗・manifest不一致・checksum不一致は記録して除外し、結果を見て反復数・条件・集計方法を変更しない。
- 実験は1台のWindows機で各言語3回、direct-first固定順。結果を別環境へ一般化せず、CPU/JIT/コンパイラの因果効果と断定しない。

## 技術的再実行の事前記録

初回のtimestamp IDを用いた3回は、全言語のベンチマークとschema検証を完了したが、隔離環境へbenchmark定義JSONをコピーし忘れたため、既定のarchive stepが失敗した。最終の固定名出力だけが残り、先行2回の出力は上書きされ、独立run単位の再計算・監査ができない。このためその3回は数値を読み出さず破棄し、主分析へ含めない。独自形式IDの事前試行はschema検証失敗のため無効。

再実行前の措置: benchmark定義JSONを隔離環境へコピーし、各run直後にarchiveされた個別JSONの存在を確認する。元の条件・3実験/言語・統計・除外規則は変更しない。これは公開不能となった技術失敗バッチの置き換えであり、失敗バッチの測定値は公開・比較しない。

archive stepも隔離下の `.pending` ファイル作成でOSアクセス拒否となったため、各runでschema検証成功した固定名出力3件を直ちに `results/raw/<experiment_id>/` へ複写する。これはarchiveツールを介さないraw保管であり、複写完了を確認してから次runへ進む。rawファイルを一切数値閲覧せず、計画済み3runを完了した後に一括分析する。

raw保管バッチのメタデータ確認で、stage内のmanifest配置階層が誤り、3言語とも `provenance=unavailable` になったことを検出した（計時値・samplesは読んでいない）。このため同バッチは主分析から破棄する。再実行前に `artifacts/function-call-analysis/manifest.json` のパスをrunnerの期待位置へ修正し、出力の `provenance=matched` とsource/runtime/options一致を各runで機械確認してから数値分析する。反復数は言語ごと3回のまま置き換える。

最終採用バッチのexperiment IDは、既存validatorのtimestamp形式要件を満たすため事前に与えた一意ラベルであり、その数字部分は実際の開始時刻と一致しない。実際の時刻は各resultの `created_at` と `run_id` に記録されているため、ID prefixを時刻証拠として解釈しない。公開集計はraw JSONに記録されたSHA-256で結び、IDは対応付けだけに使う。

表示値再計算では元実装の丸め差（CPythonのties-to-even、JavaScriptのMath.round、Cのprintf）を考慮し、元JSONの平均・中央値と生sample再計算の差が0.001001 ms以内であることを照合する。公開集計は生sampleから一律half-upで再計算する。
