# Issue Automation Dashboard / Gate protocol

Issue #80（承認済み18節・V3.3）の実装。Web Dashboard、benchmark semantics、manifest v2、既存artifactは変更しない。updaterは観測・評価・同一コメントの更新だけを行い、dispatch / cancel / rerun / merge / Issue close / branch削除のAPIを持たない。

## Stateと移行

`.github/automation-dashboard.json` はtrusted main上の登録・信頼・必要条件のpolicy。runtime stateをrepositoryへcommitしない。Issue #80では既存comment `5979234464` を明示bindし、新しいコメントを作らない。今後のIssueのcomment IDがnullなら、許可authorの一意なDashboardを再利用し、無ければserialized writerが一度作成する。

同一コメントに人間用Markdownと `langbench-automation-state:v1` のJSONを保存する。repository / Issue / purpose、actor、action別owner、active action / purpose / dedup key / dispatch state / run ID、全dispatch ledger、PR / head、Work / CI / public-data / requirements / conditions、merge / exact sync、blocker / FOLLOW_UP / last transition / UTC更新時刻を保持する。`null`、`PENDING`、`NOT_REQUIRED` は別の値。

JSONは表示cacheであり、PASSの根拠ではない。旧MarkdownのPASSを解析・移植しない。Issue #80のowner / task / keyは開始時に読んだ承認Issue・最新Dashboardの公開事実をpolicyへ明示登録し、移行時も保持する。他の旧Issueは登録されるまで変更しない。未知schema、壊れたJSON、policyとのownership/requirements矛盾は `SAFE_STOPPED / ERROR`。未知JSONを上書きせず停止表示を付ける。stateのPR bindが別PRに変わる場合も停止し、黙って候補を選び直さない。

## Eventsと競合

PR open / synchronize / edited / merge等は `pull_request_target`、Work・dispatch・artifact・smoke更新は `issue_comment`、CI / Windows / sync完了は `workflow_run` で再照合する。`pull_request_review` はPR merge refを使うため、write tokenを持たない `Observe PR review event` bridgeを経由し、trusted default branchの `workflow_run` observerを起こす。bridgeはcheckoutしない。イベントpayloadのSHAやPASSを証拠に使わない。

updaterは許可Issueと同一RefsのPRをGitHub APIから再取得し、workflow ID/path/repository/head/eventとrequired jobs/stepsを照合する。全ページを読み、不完全な取得はfail-closed。CIは最新run/attemptを使い、古い成功を新retryの進行中状態へ流用しない。最新headが存在すれば古いreviewの後着は無視し、新headの結果がない場合は `STALE` / `PENDING`。

repository単位のActions concurrency（cancelなし）でwriterを直列化する。毎回最新factを二度収集し、一致した場合だけ更新する。JSONが同じなら書き込まず、updated時刻も変えない。comment作成も二度確認する。更新後PRが変わった場合は同じコメントを `STALE / SAFE_STOPPED` に修復する。GitHub comment PATCHはCASを提供しないため、**このworkflowが唯一のstate writer**であることが運用条件。ownerはstate JSONを直接編集せず、後述receiptを投稿する。変更直後から次イベントまでの一時的な観測遅延はあり、DashboardのPASSはAPIのmerge権限や自動mergeではない。

bot自身のcomment editは `sender` で除外する（元authorがownerであっても）。定期pollは主経路にしない。取りこぼし回収の手動 `workflow_dispatch` はmain限定で、observer自身はdispatchしない。

## Workの信頼境界

Issue #80の既登録独立Work automationは `6ac2312d9a3481919a778124d511b885`。接続Workが実際に投稿するGitHub authorは `tetsujisugimori-coder` / user ID `265440097` / type `User`。このauthor三要素、automation ID、record kind、repository、Issue、PR、full head SHAをすべて照合する。任意authorの同文、単なる `WORK_REVIEW_PASS` 文字列、GitHub APPROVEDだけではWork PASSにならない。

WorkはPRに以下の**単独JSONコメント**を投稿する。以下は仕様例であり、実際のレビュー結果ではない。SHA・PR番号は実API値を使用する。

```text
<!-- langbench-work-review:v1
{"schema_version":1,"kind":"work_review","repository":"tetsujisugimori-coder/LangBench-Live","issue":80,"pr":<actual_pr_number>,"head_sha":"<actual_full_head_sha>","automation_id":"6ac2312d9a3481919a778124d511b885","verdict":"<PASS|PENDING|BLOCKED>","blockers":[],"active_blocker":null,"follow_up":[],"follow_up_recorded":true,"conditions":{}}
-->
```

`blockers` は未解決IN_SCOPE_BLOCKERのpublic要約、`follow_up` は目的外事項のpublic記録（発見Issue/PR/head・概要・重要度・今回直さない理由・将来確認箇所・新Issue候補）。空配列は明示ゼロ件。欠落をゼロ件に推測しない。`active_blocker` があればPASSにしない。Workの対象headの最新recordを使用する。GitHub changes-requested reviewは追加のveto。

automation IDは署名ではない。このGitHub accountは承認されたWorkの投稿主体という明示的trust rootであり、同じaccountを利用する人間からWorkとの暗号的区別はできない。独立Work以外によるこのrecordの代筆は禁止。本実装taskは実Work PASSを投稿しない。別GitHub Appを使う運用へ移る場合は、人間承認のauthor/app identity変更をtrusted policyへ反映する。author照合はrepo権限や文章内actorの自己申告で代替しない。

必要なWindows / integrity条件は `conditions.<name>` に `status` / `head_sha` / `run_id` を記録する。updaterは正式workflowのAPI結果を再取得し、main / target SHA / workflow_dispatch / successを照合する。artifact integrityは追加で `artifact_id` / `sha256` を必要とし、GitHub artifactのrun ID・expired=false・digestに一致することを確認する。測定結果PRは `pr` と実merged main PRを照合する。失敗/未確認をNOT_REQUIREDへ変換しない。Issue #80の実装PRではWindows実測・validation・artifact実測検証・結果PRは承認仕様によりNOT_REQUIRED。

公開recordへtoken、秘密情報、期限付きURL、ローカルprivate pathを入れない。updaterの例外ログはAPI応答やURLを表示しない。syncレポートはpublic SHAと保持数だけを出す。artifactはbounded ZIP内の単一JSONとして読み、展開・import・実行しない。GitHub bearer tokenを外部artifact redirectへ転送しない。

## Merge Gate

open / non-draft / main PR、full current head、同headのWork PASS、必須Ubuntu・WindowsのPython tests workflow/job success、公開データを検算するunittest step success、必要なWindows / integrity / result PR条件、IN_SCOPE / active / ownership blockerなし、PR titleの `Issue #80`、本文の `Refs #80` と `Current head: <full SHA>` を同時に要求する。`Closes` / `Fixes` / `Resolves` のIssue auto-closeは禁止。JSON由来の前回Gate PASSを流用しない。

Gateは `PASS / PENDING / BLOCKED / STALE / ERROR` と理由を返す。PASSのみ `READY_FOR_HUMAN_MERGE`。人間mergeを代行しない。導入PRが未mergeの間、GitHubのdefault branchにはupdaterがまだ無いため、Hosted fixture CIと独立Workで審査し、正式運用はtrusted mainへの人間merge後に始まる。

## Exact sync / Completion Gate / live smoke

GitHub APIのmerged / merged_at / merged_by User / exact merge SHAから `MERGED_SYNC_PENDING`。既存正式 `pull-local-main.yml` のownerと起動方式を維持する。`verify-merge` と `pull-main` job successだけでなく、成功したsync scriptが出す `sync-report.json` をartifactとして取得する。repository / PR / PR head / merge SHA / target SHA / after SHA / run ID / attempt / safety success / protected-preserved / before SHA / file数を照合する。**target=exact merge SHA**のみ `LOCAL_SYNCED`。mainが先へ進み旧mergeを含むだけのsyncをこのIssueのexact成功には使わない。

sync scriptは従来のfast-forward、tracked / operations / locks / untracked / ignored / path / hashes / origin / remote main再確認を維持する。reportはすべての確認後にだけ生成し、workflow成功とartifact digestの両方を要求する。旧runにレポートが無ければ成功を推測せず停止する。

Issue #80ではmerge後、同一commentに `LOCAL_SYNCED` が表示されることをownerが確認し、最小live smokeとして以下をIssueに記録する（実値のみ）。observerは次のcomment eventでCompletion Gateを再計算する。

```text
<!-- langbench-live-smoke:v1
{"schema_version":1,"repository":"tetsujisugimori-coder/LangBench-Live","issue":80,"pr":<actual_pr>,"merge_sha":"<actual_full_merge_sha>","dashboard_comment_id":5979234464,"sync_run_id":<actual_run_id>,"observed_state":"LOCAL_SYNCED","status":"PASS"}
-->
```

人間merge、exact sync、必要post条件、同head Work/no blocker、FOLLOW_UP明示記録、live smokeがすべて成立して `COMPLETED`。Issue closeはobserverが実施せず、ownerがCompletion Gateと最新APIを確認して行う。未merge PRのself-hosted実行、検証だけの性能測定は禁止。

## Ownership / dedup

implementation / fix / Windowsは本担当Work（owner継続watchdogのみ継承）、reviewは独立Work、local syncは正式workflow。observerは非dispatch actor。初期taskのtargetは承認main `c5ca7a3499fdc6f61f43ec5935861db2e9d3f5fd`、実task IDは `01a10698-73a4-7739-ad30-70d1671370de`、attempt=1。active ledgerを保持し、追加taskを起動しない。

ownerの外部preflightとdispatch確認後、Issueに `langbench-dispatch-receipt:v1` 単独JSONを投稿して記録を更新できる。

```text
<!-- langbench-dispatch-receipt:v1
{"schema_version":1,"repository":"tetsujisugimori-coder/LangBench-Live","issue":80,"dispatch":{"target_sha":"<full_sha>","action_type":"<registered_action>","purpose_id":"<stable_purpose>","dedup_key":"tetsujisugimori-coder/LangBench-Live:issue80:<full_sha>:<registered_action>:<stable_purpose>","state":"<REQUESTED|DISPATCHING|RUNNING|SUCCEEDED|FAILED|CANCELLED|UNKNOWN>","run_id":"<actual_run_or_task_id>","attempt":1,"retry_of":null}}
-->
```

これは外部runの観測結果のowner attestationで、コメント投稿によるdispatchではない。updaterはreceiptを起動・再試行許可に使わない。同keyでRUNNING/SUCCEEDEDが複数あれば `DUPLICATE_DISPATCH_DETECTED / BLOCKED`。REQUESTED / DISPATCHING / UNKNOWNは外部照合待ち。retryは同keyのattempt / retry_ofで記録する。ownerだけが正本と取消可否を決め、同じrunのreceiptを更新する。ledgerの削除、別purposeへの偽装、非owner receiptでの上書きは禁止。

ownerが新しいactive actionへ切り替えるときは、receiptのtop-levelへ `"active": true` を明示する。updaterはowner-authenticatedの最新receiptだけからactive action / purpose / key / run IDを切り替え、ledgerを残す。同じactive runのstateはそのreceiptの外部観測結果に追従する。active指定そのものはdispatchを発生させない。

## 検証と未確認

`python -B -m unittest tests.test_automation_dashboard -v` は24受入fixtureを番号付きで確認し、追加trust/API regressionsも含む。既存 `Python tests` のunittest discoveryに含まれ、Hosted Ubuntu/Windowsで同じfixtureが実行される。既存Hosted Windows sync safety suiteへreport identityのfixtureを追加した。

導入PRの実Hosted CI、独立Work、実merge/sync/live smokeはそれぞれ取得後に確認する。Cloud Linux fixture成功をWindows実機成功としない。Windows性能実測は実行しない。FOLLOW_UP: 任意の旧Issue登録、Work専用GitHub Appによるより強いidentity分離、取りこぼしwatchdogは本IssueのGateを迂回せず、今後必要な時に承認する。
