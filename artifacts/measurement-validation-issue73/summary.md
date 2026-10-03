# Issue #73 Windows measurement provenance validation

## 結果

Windows self-hosted runnerで、trusted `main` の measurement provenance / manifest v2 経路をend-to-endで検証した。対象は `function_call_numeric_sum` の Count=1 / `direct_first` で、正式workflowのauthorize、独立clone、3言語実行、archive、manifest v2 validator、comparison controls、artifact uploadまで成功した。

今回の小規模validationはprovenance / manifest v2基盤のWindows実機検証を目的としており、性能優劣について新しい結論を出すものではない。

## 実行とintegrity

- Issue: #73
- trusted main SHA: `7dd02f639b54ca2a57571c29405258ce3c2c31c2`
- human-merged PR: #78
- 正式同期run: `37122955826`
- Windows validation run / attempt: `37123211456` / `1`
- 実行runner: `ギャラリア`
- 専用labels: `self-hosted` / `Windows` / `X64` / `langbench-live-tetsu-windows`
- authorize job: `111203251005` — success
- validate job: `111203287581` — success
- artifact ID: `11273992732`
- artifact name: `measurement-validation-issue74-run37123211456-attempt1-7dd02f639b54`
- artifact size: 4262 bytes
- artifact ZIP SHA-256: `df8588ccae1ba0e39fc85d0a6e5808da008419e044384c1b0e90053924f8b054`
- ZIP取得・展開: success
- ZIP構造検査: success
- `files.sha256.json`: 展開後7ファイルすべて一致
- Workの実ZIP再取得完了: `2026-10-03 12:54:44 UTC` / `21:54:44 JST`（独立レビュー側の取得記録）
- Local Codexの今回の実ZIP再取得完了: `2026-10-03 13:55:25 UTC` / `22:55:25 JST`（上記Work記録とは別の取得）

artifact名の`issue74`は準備workflowで固定された識別子である。検証・公開サイクルの主キーはIssue #73で、実行identityは`execution.json`と本summaryに記録した。

## 公開バイトの保持

PR #79の初回公開ではGitのtext変換で原artifactのCRLFがLFになり、7対象中5件がhash不一致になった。原ZIPの8ファイル（hash一覧を含む）を原バイトのまま復元し、対象JSONとREADMEだけに `.gitattributes` の `-text` を適用した。生成時のLF/CRLF混在を保持し、公開用の改行正規化は行わない。hash一覧、ZIP digest、manifest、source/runner hash、測定値は変更していない。人間向けの本summaryは原ZIP外で、展開後7ファイルのhash対象には含まれない。

## 実provenance

| 言語 | Windows実機で確認した値 |
|---|---|
| C | Windows / x64、native、GCC `gcc (Rev5, Built by MSYS2 project) 16.1.0`、`-O2 -std=c11 -Wall -Wextra` |
| Python | Windows / AMD64、Python `3.14.7`、CPython `3.14.7`、`optimize=0` |
| JavaScript | Windows_NT / x64、Node.js `v24.20.0`、V8 `13.6.233.17-node.53`、`exec_argv=[]`、`NODE_OPTIONS`空 |

全言語についてsource hash、runner hash、run ID、measurement orderをmanifest v2に記録した。観測できない値を推測で補っていない。

## Validatorとcomparison

- archive reader: valid
- measurement manifest v2 validator: valid
- manifest SHA-256: `ac6fcf2c371b75112d476b5fffd3428b45b46719da7d95096989bf02bdd557e9`
- comparison match control: C / Python / JavaScriptすべて`exact_applicability=true`
- missing / mismatch / unknown controls: 全言語で`exact_applicability=false`
- archive identity control: comparable
- legacy archive comparisonのmissing/cautionは別記録のまま昇格しない

comparison controlsは合成入力によるfail-closed動作確認だけに使用した。実測order coverage、最適化解析、性能差の証拠ではない。

## 公開範囲と未確認事項

公開物はartifact内のmanifest、archive index、experiment definition、validation、comparison controls、execution identity、展開ファイルhash、説明文と本summaryに限定した。rawのC / Python / JavaScript結果はrepositoryへ追加しない。`archive.json`にexcluded rawのhashが残るが、rawファイル自体が公開bundleに含まれるという意味ではない。

過去の失敗run `37119062192` ではrunner内部の`runs.json`と`run-01.log`を取得できなかったため、過去実機の直接原因は未確定である。Issue #77では修正前の正式script経路でCount=1の一文字引数化をコード再現し、修正後Hosted Windows回帰と今回の実機E2E成功を確認した。このコード再現と過去runの直接原因は区別する。
