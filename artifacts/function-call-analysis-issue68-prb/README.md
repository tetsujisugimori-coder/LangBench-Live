# Issue #68 PR-B: Windows 実機解析公開記録

## 入力と検証

- analysis ID: `issue68-pra-69-36797708544`
- 信頼済み解析 code SHA: `98dbb01d36c204f352d5b4690de72b570fdb075e`
- Actions artifact ID: `11133909890`（run `36797842951`）
- 取得した ZIP の SHA-256: `116c37289b674b477640ab0d02273ce1c6ad46b51a136fa1c72cdc34cc0a19fb`
- ZIP: 37 entries、integrity check 成功。展開後、repository の `tools/validate_function_call_analysis.py --expected-sha 98dbb01d36c204f352d5b4690de72b570fdb075e` で `analysis_package=valid`。
- `upload-manifest.json`: 36 included files、0 excluded files、0 redacted files。36ファイルの upload SHA-256 を取得物の実バイトから再計算し、すべて一致。記録上の raw/upload SHA-256 も全件一致し、`raw_kept_separate_from_upload=true`。runner 上の raw package は取得もcommitもしていない。
- PR #67 の公開測定 manifest: `artifacts/direct-function-call-balanced-order/manifest.json`、SHA-256 `60a5b14eeb8f287910b248e832a177264593682eda3952f06219e4a13a49c4a4`、code SHA `fde3f78b385034248bac9dfe7a97c8da37ffb3ae`、series `issue66-balanced-final-01`、issue 66、benchmark `function_call_numeric_sum`、status `completed`。

## 公開範囲

`analysis-package/` には取得した upload artifact から、manifest、provenance、upload manifest、validation、C の GCC report/assembly、Python bytecode、JavaScript の両順序 trace と order findings をバイト同一で収録した。provenance の evidence SHA-256 と各ファイルを validator が照合する。`comparison-reviewed/comparison.json` と `comparison-reviewed/comparison.md` は、この公開packageとPR #67公開manifestから生成した。比較内の各evidenceは元artifact上の `original_path` と、repository rootから辿れる `published_path` を別々に記録し、生成時に後者の6ファイルすべての実在・SHA-256一致を確認した。

取得artifactに含まれる `stage-logs/` 26件と `run-state.json` はPR差分には含めない。これらは取得元artifactに残り、`upload-manifest.json` にupload時の一覧とhashがある。PR差分内の公開evidenceは、第三者がvalidatorと比較器を実行できる範囲を揃えた。取得ZIPそのものとself-hosted runnerのraw packageはcommitしない。

## 再導出した所見と照合境界

| 言語 | source | 条件照合 | 解析所見 |
|---|---|---|---|
| C | PR #67と一致 | GCC 16.1.0、x64、compile options、両順序coverage一致。exact=true | `main.s` に対象 `add` 呼出が残り、direct pathにSSE2命令。inlining未検出、vectorization/SIMD検出。 |
| Python | PR #67と一致 | CPython 3.14.7、x64、両順序coverage一致。ただし解析options `["optimize=0"]` と測定options `[]` が異なる。exact=false | bytecodeに `LOAD_GLOBAL add` と `CALL 2`。inlining/vectorization未検出、SIMD未確認。 |
| JavaScript | PR #67と不一致 | Node.js v24.20.0、x64、空options、両順序coverage一致。測定manifestにV8 versionがないためimplementation一致は未確認。exact=false、source差の影響はunknown | `direct_first` と `function_call_first` の双方で対象 `add` / `called` の最適化とinliningをtraceから検出。vectorization/SIMDは未確認。 |

JavaScript解析条件のV8は `13.6.233.17-node.53`。Node.js版が一致してもV8版の一致とは扱わない。Python `optimize=0` は解析時の明示条件であり、測定manifestの空optionsと意味上同一に正規化する根拠は公開資料にないため、そのまま不一致とした。traceは性能本測定ではなく、所見と測定差の因果関係は確立していない。

比較JSONには測定/解析それぞれのsource、runtime、implementation、version、architecture、options、測定順序、解析coverage、findings、evidence hash、条件hash、判定理由、trace flags、両順序findingsを記録した。条件hashはcondition objectをキー順・空白なしのJSONにしてSHA-256を計算した値で、元manifestの値ではなく再導出値である。

## Workレビュー指摘の分類

| 項目 | Severity | Scope | Merge blocking | Action |
|---|---|---|---|---|
| 実機公開物の欠落 | P1 | IN_SCOPE_BLOCKER | yes | 検証済みartifactの必要なevidence、manifest、provenance、comparisonを新規保存先へ公開。 |
| V8と両順序coverageの未検証 | P1 | IN_SCOPE_BLOCKER | yes | runtime/implementationとversionを分離し、両順序coverageをexact条件に追加。欠落/未知はfail closed。 |
| PR #67測定manifestへの未束縛 | P1 | IN_SCOPE_BLOCKER | yes | 実ファイルのSHA-256、series、code SHA、issue/benchmark/statusを照合し、不一致は出力前に拒否。 |
| Python options fixture不一致 | P2 | IN_SCOPE_MINOR | yes | 実物のoptions差をfixtureと出力へ反映し、Pythonを非exactと記録。 |
| 再レビュー: evidence pathが旧資料を参照 | P1 | IN_SCOPE_BLOCKER | yes | 元pathと公開pathを分離し、公開pathの実在・hashを生成前に検証。 |
| 再レビュー: PR本文が旧内容 | P2 | IN_SCOPE_MINOR | yes | PR本文を現headの完全版へ更新。レビュー投稿後にGitHub上の本文更新を確認。 |

PR #62とPR #67の既存公開測定ファイルは変更していない。PR #62は9 runs/900 samples、PR #67は12 runs/36 language runs/3600 samplesの公開検算を通した。
