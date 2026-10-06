# Issue Automation Dashboard / Gate protocol

Issue #80（承認済み18節・V3.3）の実装。Web Dashboard、benchmark semantics、manifest v2、既存artifactは変更しない。updaterは観測・評価・同一コメントの更新だけを行い、dispatch / cancel / rerun / merge / Issue close / branch削除のAPIを持たない。

## Issue #83: 表示・診断情報

`tools/automation_dashboard.py` の `render()` が表示専用の
`tools/automation_dashboard_display.py` を使う。入力stateの変更、現在時刻の取得、
API呼出し、証拠の補完は行わない。末尾のv1 JSON marker・JSONの直列化・parser・
Gate・状態遷移・writer・イベント経路・ownership・dedup・保存形式は従来どおり。
表示上のSHA一致は文字列の照合説明であり、機械Gateの再認定ではない。

V3.4第34節では、Dashboard・イベント更新・Gate・merge後CI保持・修正PR handoffが
既存実装、第35〜43節の受領／開始・監視record・期限回収は追加運用要件とされている。
後者はこの表示PRで実装しない。規則の記載やDashboard更新時刻だけでは
実監視成功・実進捗・停止・期限到来確認の成立を推測できない。

実装内の `initial_state()` / `evaluate()` / updaterの安全停止経路が使用する
current_stateの対応表は次のとおり。V3.4の運用状態をこの表へ追加して
実装済みと見せることはしない。

| 機械コード | 日本語の説明 |
|---|---|
| IMPLEMENTING | 実装中 |
| REVIEWING | レビュー・検証の確認待ち |
| FIX_REQUIRED | 修正または阻害条件の解消が必要（修正開始は別確認） |
| READY_FOR_HUMAN_MERGE | 条件成立・人間のマージ判断待ち |
| MERGED_SYNC_PENDING | マージ済み・正式同期の確認待ち |
| LOCAL_SYNCED | 正式同期済み・完了条件の確認待ち |
| COMPLETED | 必須完了条件が成立 |
| SAFE_STOPPED | 安全停止・根拠の確認または判断が必要 |

| 証拠・Gateコード | 日本語の説明 |
|---|---|
| PASS | 条件成立 |
| PENDING | 確認待ち |
| BLOCKED | 阻害条件あり |
| STALE | 対象または証拠が古い |
| ERROR | 根拠・状態を検証できない |
| NOT_REQUIRED | 今回の承認済み範囲では不要 |

dispatchは既存のREQUESTED / DISPATCHING / RUNNING / SUCCEEDED / FAILED /
CANCELLED / UNKNOWNをそのまま表示する。REQUESTEDは依頼記録であり、受領・開始を
意味しない。未知コードは原文＋「説明未定義」、欠損は「未取得」。空配列による
明示ゼロ件と欠落も区別する。NOT_REQUIREDと証拠未取得は別々に表示する。

表示順は状態・両Gate・blocker、Issue／PR／head／merge、Work／Ubuntu／Windows／
公開データ、正式同期／live smoke／必要条件、担当／dispatch、診断詳細／履歴／
FOLLOW_UP／遷移／Dashboard最終更新。blockerと未確認の証拠は折りたたみの外に置く。
主要証拠にはstatus、元reason、stateにある対象SHA・run ID・attempt・Work comment IDを
表示する。現在headを証拠のheadに補完しない。PR head、merge SHA、sync targetも区別する。
未取得フィールドがあるPASSは元のPASSを保持し、診断値だけ「未取得」とする。
これは証拠収集の拡張ではない。

Issue／PR／commit／Actions run／Work結果commentのリンクは、state.repositoryが
固定の正規repositoryに一致し、IDが正の整数（同期runの数値文字列を含む）または
SHAが40桁の小文字hexである場合のみ生成する。リンクの生成は外部APIでの存在確認を
行わず、既存parser／証拠取得経路が与えるstateを表示する。任意URLをリンクとして
取り込まない。Cloud task等はIDの文字列だけを表示し、URL形式を推測しない。
自由文・HTML・Markdown・改行・table separator・marker類似文字列をエスケープする。
全証拠フィールド、全owner、全dispatch履歴は診断詳細と機械JSONに保持する。

`last_updated` は **Dashboard最終更新**。元のtimezone付きUTC値を保持し、JSTを
併記する。日付跨ぎも変換する。欠損は「未取得」、不正・timezoneなしは元値と
「JST: 解析不能」を表示し、現在時刻で補完しない。最終監視成功／最終作業進捗という
ラベルは使わない。正常待機・人間待ち・安全停止を監視停止と同一視しない。

### Markdown表示例（合成fixture・主要行の抜粋）

以下は受入確認用の合成例。Issue #83の実Gate・レビュー・CI結果ではない。
省略した行にも元stateの診断値が表示される。GitHub上でこのdocsのMarkdownを
確認でき、同じ組合せは `tests/test_automation_dashboard_display.py` でも検証する。

変更前は辞書全体が現在値セルに表示された。

| 項目 | 現在値 |
|---|---|
| Current state | READY_FOR_HUMAN_MERGE |
| Work review | {"status": "PASS", "reason": "Authenticated Work review for current head", "head_sha": "対象head", "comment_id": "結果comment"} |
| Last updated (UTC) | 2026-10-05T15:30:00Z |

変更後（人間マージ待ち）：

| 項目 | 現在値 |
|---|---|
| 現在状態 | READY_FOR_HUMAN_MERGE — 条件成立・人間のマージ判断待ち |
| Merge Gate | PASS — 条件成立 / 理由: All required evidence is current and successful |
| Completion Gate | PENDING — 確認待ち / 理由: Human merge is not confirmed |
| 現在のblocker | なし（stateの明示的な空配列） |
| Workレビュー | PASS — 条件成立 / 理由: Authenticated Work review for current head / 対象head SHA: 対象head / 現在PR headと一致 / Work結果comment ID: 結果comment |
| Dashboard最終更新 | 2026-10-05T15:30:00Z（元値） / JST: 2026-10-06T00:30:00+09:00 |

CI待ち（監視停止とは判定しない）：

| 項目 | 現在値 |
|---|---|
| 現在状態 | REVIEWING — レビュー・検証の確認待ち |
| Merge Gate | PENDING — 確認待ち / 理由: Workflow is not completed |
| Ubuntu CI | PENDING — 確認待ち / 理由: Workflow is not completed / 対象head SHA: 未取得 / 照合未確認 / Actions run ID: 対象run / run attempt: 未取得 |
| live smoke | REQUIRED — 今回の必須条件 / 未取得 |
| Windows実機測定 | NOT_REQUIRED — 今回の承認済み範囲では不要 / NOT_REQUIRED — 今回の承認済み範囲では不要 / 理由: Explicit trusted policy |

安全停止（通常の確認待ちとは区別）：

| 項目 | 現在値 |
|---|---|
| 現在状態 | SAFE_STOPPED — 安全停止・根拠の確認または判断が必要 |
| Merge Gate | ERROR — 根拠・状態を検証できない / 理由: Trusted facts/schema could not be verified |
| Completion Gate | ERROR — 根拠・状態を検証できない / 理由: Trusted facts/schema could not be verified |
| Dashboard最終更新 | 未取得 |

完了（COMPLETEDとMerge Gate BLOCKEDの併存）：

| 項目 | 現在値 |
|---|---|
| 現在状態 | COMPLETED — 必須完了条件が成立 |
| Merge Gate | BLOCKED — 阻害条件あり / 理由: PR already merged; no merge authorization / マージ済みのため、新たなマージ許可の対象外。COMPLETEDは完了条件の成立、Merge Gateは新たなマージ許可を表すため併存します |
| Completion Gate | PASS — 条件成立 / 理由: All required evidence is current and successful |

### 制約・FOLLOW_UP

表示のみの変更なので、同一stateの再処理は既存writerのNO-OPを維持し、コメントや
更新時刻を増殖させない。未知schema・壊れたstateは既存の安全停止を維持する。
既存テストのIssue #80 policyやIDは合成回帰fixtureとしてのみ使用し、#83の運用へ
流用しない。Issue #80の閉じたコメントをこの作業で更新しない。

- Issue #83開始時のtrusted-main policyはIssue #80のみを登録している。#83固有の
  policy／Dashboard／独立レビューbindが正式経路で成立するまでは、#83の
  READY_FOR_HUMAN_MERGEは未確認。登録・認証・owner変更はこの表示PRの変更対象外。
- V3.4の監視record取り込み・期限確認経路はこのPRで追加しない。実起動経路・登録ID・
  次回予定が確認できない期限は「期限保証不能」。設定保存と受領・開始を区別する。
- 既存F1「将来REQUIRED Windows条件のPR head／merge SHA分離」は今回もFOLLOW_UP。
  condition生成とphase policyの変更は別の承認範囲で扱う。
- Hosted Ubuntu／Windows CI、独立Work、正式同期、live smokeは各実head／mergeと
  対応する実証拠で別々に確認する。未マージコードのself-hosted実行・性能測定をしない。

## Stateと移行

`.github/automation-dashboard.json` はtrusted main上の登録・信頼・必要条件のpolicy。runtime stateをrepositoryへcommitしない。Issue #80では既存comment `5979234464` を明示bindし、新しいコメントを作らない。今後のIssueのcomment IDがnullなら、許可authorの一意なDashboardを再利用し、無ければserialized writerが一度作成する。

同一コメントに人間用Markdownと `langbench-automation-state:v1` のJSONを保存する。repository / Issue / purpose、actor、action別owner、active action / purpose / dedup key / dispatch state / run ID、全dispatch ledger、PR / head、Work / CI / public-data / requirements / conditions、merge / exact sync、blocker / FOLLOW_UP / last transition / UTC更新時刻を保持する。`null`、`PENDING`、`NOT_REQUIRED` は別の値。

JSONは表示cacheであり、PASSの根拠ではない。旧MarkdownのPASSを解析・移植しない。Issue #80のowner / task / keyは開始時に読んだ承認Issue・最新Dashboardの公開事実をpolicyへ明示登録し、移行時も保持する。他の旧Issueは登録されるまで変更しない。未知schema、壊れたJSON、policyとのownership/requirements矛盾は `SAFE_STOPPED / ERROR`。未知JSONを上書きせず停止表示を付ける。stateのPR bindが別PRに変わる場合も停止し、黙って候補を選び直さない。

## Eventsと競合

PR open / synchronize / edited / merge等は `pull_request_target`、Work・dispatch・artifact・smoke更新は `issue_comment`、CI / Windows / syncの開始・完了は `workflow_run` の `requested / in_progress / completed` で再照合する。GitHubはrerunで `requested` を発行しないため、retryは `in_progress` でも旧PASSを失効させる。`pull_request_review` はPR merge refを使うため、write tokenを持たない `Observe PR review event` bridgeを経由し、trusted default branchの `workflow_run` observerを起こす。bridgeはcheckoutしない。イベントpayloadのSHAやPASSを証拠に使わない。

updaterは許可Issueと同一RefsのPRをGitHub APIから再取得し、workflow ID/path/repository/head/eventとrequired jobs/stepsを照合する。全ページを読み、不完全な取得はfail-closed。CIは最新run/attemptを使い、古い成功を新retryの進行中状態へ流用しない。最新headが存在すれば古いreviewの後着は無視し、新headの結果がない場合は `STALE` / `PENDING`。

repository単位のActions concurrency（cancelなし）でwriterを直列化する。毎回最新factを二度収集し、一致した場合だけ更新する。JSONが同じなら書き込まず、updated時刻も変えない。comment作成も二度確認する。書込後にPRだけでなくCI run / attempt / jobs / steps、Work、review、必要条件run / artifact / result PR、正式sync run / safety report、smoke / receiptを含むGate factsを再取得する。変化を検出したら最新factsで表示を更新し、同じcommentの両Gateを `STALE / SAFE_STOPPED` へ失効させる。再取得失敗や破損はmainの `safe_stop` を通し `ERROR`。新規comment作成時のID確定だけは正当な変化として扱う。

GitHub comment PATCHはCASを提供しないため、**このworkflowが唯一のstate writer**であることが運用条件。ownerはstate JSONを直接編集せず、後述receiptを投稿する。二度の事前照合と書込後照合は完全な原子性を保証しない。最終照合後の変化、GitHub API反映、event配送、Actions queueの遅延中には表示の観測遅延が残る。queued rerunは `requested` が無いため開始時の `in_progress` まで観測が遅れる場合もある。開始／retryイベントでもAPIから再評価し、旧attemptの成功を流用しない。DashboardのPASSは観測時点の表示であり、mergeの直前にも最新GitHub factsを確認する。APIのmerge権限や自動mergeではない。observer自身は追加runや回収taskをdispatchしない。

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

API IDを収集する前に、許可author・repository / Issue / PR / automation / kind・schema / head・blocker / FOLLOW_UP・conditions object・各condition object/status/head/API ID型を共通validatorで検証する。別identityのrecordはAPI選択に使わない。認証済みrecordの `conditions=["broken"]`、文字列/null、壊れたschema等は明示的な `WorkRecordError` に変換する。mainはこれを捕捉して同じcommentの旧PASSを `SAFE_STOPPED / ERROR` へ失効させ、公開の型不正理由だけを記録する。広いexceptでAttributeErrorを隠す設計にはしない。

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

人間merge、exact sync、必要post条件、同head Workと必須CI・公開データ検算、no blocker、FOLLOW_UP明示記録、live smokeがすべて成立して `COMPLETED`。Work / required_ci / public_dataはmerge前後に共通の検証条件であり、failure / pending / stale / unknown / missingでは完了に昇格しない。closed PRにはopenを要求するMerge Gateを丸ごと流用せず、Completion Gateに共通検証だけを渡す。Issue closeはobserverが実施せず、ownerがCompletion Gateと最新APIを確認して行う。未merge PRのself-hosted実行、検証だけの性能測定は禁止。

FOLLOW_UP F1（独立review 5405787735）: 将来のREQUIRED Windows post条件はPR headとmerge SHAのphase policyを分離する必要がある。発見Issue #80 / PR #81 / head `ce4aee55ae5170baed53b0baac00c85486ee9c96`、severity P2、scope FOLLOW_UP、merge blocking NO、新Issue候補 YES。Issue #80はWindows条件がNOT_REQUIREDのため、R1–R3の今回loopではtargetの測定仕様を変更しない。将来確認箇所はcondition生成とpre/post phase policy。

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

### R4: merged PR CI retention and explicit repair acceptance

GitHub may remove `pull_requests` from a successful pull-request run after
merge. Only an API-confirmed merged/closed bound PR with a full merge SHA can
use that empty-list fallback. Its live API head SHA, nonempty head branch,
head/base repositories and main base must match the run; official workflow
path/ID, pull_request event, both run repositories, latest run/attempt,
attempt-specific jobs and required unittest steps are still checked. A
nonempty association for another PR never falls back to SHA; open PRs still
require their number. No cached/manual CI PASS is used.

A post-merge fix receipt targeting the bound merge prevents Completion until
an explicit owner handoff. The owner, after the repair PR exists, publishes
one authenticated `langbench-pr-handoff:v1` JSON envelope on the same Issue:
`schema_version: 1`, `repository`, `issue`, `repair_pr` (actual new PR number),
and `previous_state` (the full current machine state, including old PR,
exact-sync evidence and dispatch ledger). This is an acceptance operation,
not a dispatch or Work review. Do not edit the Dashboard JSON or create a
second Dashboard comment. The archive must match the currently bound cycle;
the collector re-fetches the old merged PR identity and new Issue-referencing
PR. Ambiguous/corrupt records fail closed. Publish one handoff, rather than
editing the archived historical state. Repair head changes are re-read from
GitHub and invalidate old evidence normally.

The existing schema/writer and comment ID remain unchanged. The archived
owner record retains the prior #81 exact sync and dedup history; the live
ledger also remains intact. A new bound repair PR must independently satisfy
same-head Work/Hosted CI/required conditions, human merge, its own exact merge
sync and same-comment live smoke before Completion. The implementation actor
does not author the handoff, Work PASS or smoke PASS. The owner must resolve
DISPATCHING receipts explicitly; an unknown ownership state still blocks.
F1 remains FOLLOW_UP. Snapshot checks detect observed races but cannot provide
atomicity across GitHub APIs or eliminate event observation latency.

Subsequent repairs retain every earlier handoff record. The records must form
one directed chain: each source and target occurs once; forks, joins, duplicate
comments, disconnected chains and cycles fail closed. For the current bound PR,
its outgoing handoff is the next transition and takes precedence over the
incoming historical handoff. If no outgoing record exists, replay uses the
incoming record idempotently. The next transition's archived head, merge,
exact-sync evidence and ledger must still match the current cycle. Historical
records are neither deleted nor edited to select the next repair.


## Issue #86: register #85 before implementation

Issue #85 is explicitly registered for `archive-samples-summary-only`. Its
`initial_dispatch: null` means no task has been dispatched, rather than an
unknown or successful task. A missing `initial_dispatch` remains an error.
The initial state is `AUTOMATION_ARMED`, with an empty dispatch ledger and
null active action, purpose ID, dedup key, dispatch status and run ID. This
uses the existing v1 fields/markers; only this explicit policy choice permits
the undispatched combination. Existing #80 policy/receipts remain unchanged.

A first real owner-authenticated `langbench-dispatch-receipt:v1` on Issue #85
must include `active: true` and the existing validated dispatch fields, with
an actual task/run ID and full target SHA. Do not put the review automation's
registration ID, the #86 preparation task, or a placeholder in `run_id`.
Registration alone is not implementation start. The receipt is registered
when its actual external execution identity/state has been confirmed by the
owner; REQUESTED/DISPATCHING/UNKNOWN do not certify started work. RUNNING or
SUCCEEDED receipts permit the pre-PR IMPLEMENTING state. Malformed receipts,
inactive-only ledgers and missing active identities fail closed. Subsequent
receipts continue using the existing owner and dedup protocol.

Before a receipt, no linked PR is bound and Merge/Completion stay PENDING.
A PR appearing without an authenticated active dispatch yields SAFE_STOPPED
and a BLOCKED Merge Gate even if its CI/review claims PASS. Empty active
identity is rejected for dispatched or bound states, and undispatched cached
PASS is rejected. The trusted-main observer remains the only Dashboard
writer. `dashboard_comment_id: null` allows its existing unique trusted
comment selection/creation; record the actual comment ID after main
application, not before.

#85 Work record identity is user `tetsujisugimori-coder` / numeric ID
265440097 / type User, plus its separately registered review automation
`6ac53eb50b2481918033960988ac8834`. This is role/execution separation on the
same account, not cryptographic independence. Record validation still checks
repository, Issue, PR, automation and full HEAD. The functional PR must have
title `Issue #85: ...` and standalone `Refs #85`. The preparation PR uses
`Issue #86: ...` and standalone `Refs #86`; mention related #85 in ordinary
prose/link only. The observer selects PRs by the exact standalone Refs line
before checking title metadata, so adding a second standalone Refs line for
#85 to the preparation PR would incorrectly bind it.

Windows validation, benchmark measurement and measurement-result PR are
NOT_REQUIRED under the approved CLI-only #85 specification. Artifact
integrity is NOT_REQUIRED because this cycle creates no measurement
artifact; this does not disable verification of the official sync safety
report/digest. Post-merge live smoke remains REQUIRED. Hosted Ubuntu/Windows
CI, public-data verification, same-HEAD independent review, human merge and
exact-sync/data preservation requirements remain mandatory.

The #86 preparation PR alone follows the approved transition review: current
full published HEAD Hosted Ubuntu/Windows CI, separate code/config review,
existing #80/mechanism regressions and human merge. Its machine Merge Gate
is unrecognized, not manually PASS. Do not transfer its CI/review to the
#85 functional PR. After human merge, confirm latest main policy/writer,
existing exact-sync run and sync-report before/after SHA/data preservation,
and actual observer-created #85 Dashboard/identity/requirements. Pre-PR
Gate PASS is not required. PR binding/review ingestion/CI/Merge Gate are
future functional-PR checks; formal sync/live smoke/Completion are future
functional-merge checks. No #85 CLI task starts from the preparation cycle.

The two event automations are registered and enabled; event receipt, target
matching, review execution and result ingestion remain unverified until
observed. PR events do not certify CI completion, deadline arrival or
no-event stagnation. Deadline guarantee is unavailable without a registered
separate path; no new timer, dot setting, writer or sync workflow is added.
