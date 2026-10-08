# I-01 PR101後の限定再開契約

Issue102のコード修正。関連: [Issue100](https://github.com/tetsujisugimori-coder/LangBench-Live/issues/100)、
[Issue96](https://github.com/tetsujisugimori-coder/LangBench-Live/issues/96)、
[PR101](https://github.com/tetsujisugimori-coder/LangBench-Live/pull/101)。
開始時に再取得したmainは `69d7ddb6e10f260aab6e3a31db81751a068182cd`。
Issue100現在要約6052718244と手動引受6055227025を再取得した。
PR101の実merge受信と既存正式ZIP照合、手動CLI/writer/smoke/停止は背景の記録であり、
新サイクルの実証、独立認定、I-01 COMPLETEには転用しない。

## 識別情報と認証の限界

| 情報 | 取得元・認証 | 表す実体・保証 |
|---|---|---|
| delivery ID | 正式Workイベントcontextをownerが観測 | 配送。再配信で変わり得る。Work実行IDではない |
| automation ID | 正式UI/toolの登録・保存設定読戻し | 登録。同一登録の複数実行を区別しない |
| conversation ID | 実会話contextが返す場合だけownerが記録 | 会話。任意文字列をサービス認証済み実行として扱わない |
| Cloud task ID | 正式Cloud task開始/読戻しが返す場合だけ記録 | 実装task。Workイベント実行ではない |
| Work run ID | 現正式tool/UIでは取得不能 | v2では必ずnull。別種IDを代入しない |
| execution capability | 当該担当でCSPRNG 256bit生成、ローカル保存。CLIが秘密所持を照合 | 担当用bearer capability。サービス発行のrun IDではない。公開IDは秘密のSHA256 |
| GitHub ref/commit | token認証の限定git-data API、現在refとcommitをGET再読取 | 対象の一回限り担当予約。Workサービスのイベント/実起動を認証しない |

owner入力はGitHub RESTでlogin/id/typeを認証したownerの観測として収集する。
同じGitHubアカウントの人間とWorkを暗号的に識別できない。受信と開始時刻の真実性は
ownerの正式context観測責任であり、自己申告を認証済みWork runへ昇格しない。
秘密capabilityを共有・Gitへcommit・公開comment・ログへ出力しない。コピーされれば
同一担当枠内の二実行を区別できないため、その場合は停止する。

## 単一担当と副作用の境界

担当枠は `refs/tags/langbench-i01-resume-<SHA256(dedup_key)>`。
keyはrepository/Issue/merge-target/purpose/owner_resume。deliveryを含めないので、
同一操作の別delivery、二つのWorkとも同じ枠で競合する。commitの正規JSONへowner、
reviewed HEAD/merge、実delivery/automation/start/context、capability公開ID、待機comment
全byte digest、許可操作・承認参照・read_onlyを固定し、merge commitを唯一parentにする。

GitHubのcreate-ref（存在しない同名ref一件の作成）が取得の原子的境界。
参加者はref更新・削除・期限切れ・再割当を行わない。CLIもPOST二種類以外を拒否する。
競合の敗者は停止し、勝者のcapabilityを代用しない。読取CLIは毎回ref/commitを再認証する。
管理者のref変更/削除は防げないので、repository管理者と参加者のこの運用条件が保証範囲。
汎用lease、取消、跨サービスtransaction、永続監視は提供しない。

| 操作 | 再実行・排他 |
|---|---|
| GitHub GET、既存ZIP取得/検算、Dashboard読取smoke | 外部副作用なし。繰返し可。現対象・否定履歴を毎回再照合 |
| ローカルcapability/cache保存 | O_EXCLで秘密を新規作成。cacheのatomic replaceはローカルだけ |
| inert予約commit作成 | コード/branchを変更しないgit object。結果不明ならrefを送らず停止 |
| 一回限りref作成 | 送信前ATTEMPTINGをfsync保存。結果不明/途中停止後は実ref/commit GET照合だけ。再送しない |
| owner共有入力更新・receipt公開・正式smoke公開・登録停止 | 本予約では自動実行を許可しない。外部副作用には各正式owner/唯一writerの経路が必要。条件未確立なら停止 |
| 手動引受 | owner-authenticatedの独立authorization commentで読取だけ継続。自動担当の取消/枠移譲ではない |

枠が他担当、UNKNOWN、API不可、資格不足、秘密消失、旧対象、ref改変なら停止する。
成否不明のref作成は保存journalのcommit SHAと実refを照合。存在未確認のまま再送しない。
書込前に停止しても予約枠は消さない。読取smokeは再開可能だが、他Workへの外部書込権限移譲は
既存担当が書かないというfencingをこの仕組みで証明できないため、阻害条件として残す。
GitHub comment POST/PATCH、全コメント取得、Actions concurrency、ローカルlockを
Work間のCASやleaseとして扱わない。Actions concurrencyは既存唯一writerだけの直列化。

## 契約・CLI・保存

`work_owner_resume.py` のhandoff v2はv1の対象fieldsに `authorization` を加える。
authorizationはkind=live_smoke/safe_stop、authorization_ref、effect=read_only。
workはrun_id=nullと従来のautomation/start/reference/timeにidentityを加える。
identityはscheme=capability_v1、public_id、source=local_csprng、
assurance=bearer_possession_not_service_run、route=automatic/manual、
conversation_id/cloud_task_id（未取得はnull）、authorization_comment_idを明示。
自動経路はauthorization_comment_id=null。手動経路は実人間承認comment IDが必須。
claim/receipt/next_actionは `execution_id` へ公開IDを束縛し、run_idを持たない。
claimにはref/commit_sha、next_actionにはeffectを加える。recheckはnull。
外部effectを申告した操作はSTOPPEDとなる。

schema正本: [preparation-evidence-v2.schema.json](schemas/preparation-evidence-v2.schema.json)
と [work-owner-resume-v2.schema.json](schemas/work-owner-resume-v2.schema.json)。
collectorは認証済み同共有inputのowner_resume ID、HEAD、待機byte binding、許可操作を再読取し、
唯一writerは現在factsから判断する。旧PASSを新protocolへ転用しない。

```sh
# 作業場所はwork/。初期化だけはネットワークを使用しない。
python -B -m tools.work_resume_claim --initialize --handoff work/handoff.json \
  --capability-file work/owner.secret --state work/reservation.json
# 出力された公開IDだけをhandoffのidentityへ保存。秘密は公開しない。
# 現入力/許可/実merge/待機/既存同期を二度再取得してから、限定refを一回作成。
python -B -m tools.work_resume_claim --handoff work/handoff.json \
  --capability-file work/owner.secret --state work/reservation.json \
  --sync-artifact-zip work/official-sync.zip
# 成功応答の実ref/commitをhandoff.claimへ保存。これは待機受領ではない。
python -B -m tools.work_owner_resume --handoff work/handoff.json \
  --capability-file work/owner.secret --state work/resume.json --github-read \
  --sync-artifact-zip work/official-sync.zip --read-only-smoke \
  --updated-handoff work/observed-handoff.json
```

read-only-smokeは実待機bytes受領と、唯一writerの同DashboardのLOCAL_SYNCED/
exact sync PASS/対象を読取り、実receiptと実操作時刻をローカルhandoffへ保存する。
正式langbench-live-smoke公開や共有input PATCHは実施しない。
予約取得には正式経路のcontents-write資格が必要。現在の通常shell接続はproxy失敗・
gh資格無効であり、この環境でlive取得成功を主張しない。人間merge後のWorkにこの資格が
存在しない場合は予約取得工程で停止する。GitHub pluginで手動に同名refを作成して
秘密所持や自動Work実行へ代用しない。

手動は別cache/新capabilityでroute=manual、claim=null。実ownerが以下の単独commentを
発行する。bindingは `work_resume_claim.binding(handoff)` の全JSONそのもの。

```text
<!-- langbench-i01-manual:v1
{"schema_version":1,"kind":"i01_manual_read_only","binding":<exact binding JSON>,"retained_automatic_status":"UNVERIFIED","allowed_effect":"read_only"}
-->
```

CLI結果はMANUAL_OBSERVEDで、自動経路のOWNER_OBSERVED/I-01一周へ昇格しない。
承認commentの発行自体は人間/正式ownerの操作で、本実装担当は代筆しない。

## 共有入力の改版とwriter照合

owner requestのoperationsは実NOT_ATTEMPTED/ATTEMPTING/UNKNOWNだけ。確定観測を
UNKNOWN要求へ戻さず、writer snapshotにexternal ID/time/settings版/input_digestと
入力履歴・否定watermarkを保持する。requestから確定観測を省くことはledger削除ではない。
実未解決要求の欠落は拒否し、同keyの異なるbindingも原則拒否する。
改版後writerが同対象・同登録IDの実readbackで解決した要求がowner領域に残る場合だけ、
現在snapshotの同digest/readback/watermark/履歴を照合して二度目の読み込みで復活させない。
公開factsは毎回収集し、snapshotのPASSを認定へコピーしない。

入力改版→最新stateとowner実観測からCLI生成→同recordのowner領域だけ投入→唯一writer照合→
保存/再読込→再生成/同record投入→二度目のwriter照合を回帰テストで検証する。
入力改版時は旧schema/実UNKNOWN・否定履歴を消さず、最新Prompt/版/時刻を取り直す。

## 人間merge後の実証と停止引渡し

1. 候補codeはHosted Ubuntu/Windowsと独立担当のコードレビューで審査する。未来のmerge、
   正式writer認定、receiptを候補の事前PASS条件にしない。独立結果は独立担当が発行する。
   修正PRの独立Refs行は新Issue102だけ。Issue100のpolicy更新と修正PR自体の正式Gateは別。
2. 新PR確定後、専用review/owner_resumeを別roleで正式登録し、実ID、Trigger、merge限定、
   Prompt全文/version/digest、enabledを正式UI/toolで読戻す。PR101停止済み登録を流用しない。
   新登録の副作用は本予約の自動権限外で、正式ownerの承認済み管理経路を使用する。
3. 人間merge後、最新main/policyと唯一writer適用を確認。新PRの実delivery/automation/startを
   取得し、Work run ID取得不能はnullのまま保持。旧PR101のeventを新mergeへ転用しない。
   新PRのstandalone Refsは102だけなので、旧Issue100のinputへ新PR番号を直接代入しない。
   本PRの限定policy変更は100の読取契約補修だけであり、102の正式レビュー/再開登録や
   policyを捏造して追加しない。現在toolにはGitHub webhook用Work登録引数が公開されて
   いない。正式UIで102専用の別review/resume IDと保存設定を取得し、正式policyの対象を
   整えるまで102の実証を停止する。この運用登録不足は候補コードレビューの前提にはしない。
   同共有recordを使う改版はそのIssue/対象の規約内で行い、旧入力履歴を保存する。
4. 実待機comment/digest/許可を再取得。秘密capability作成→担当枠取得→実ref/commit読戻し。
   資格/競合/UNKNOWNならここで停止。receiptを先に発行しない。
5. 既存正式同期run/attempt/jobs/stepsと既存ZIPを正式経路で回収し、API digest、単一report、
   exact merge=target=after、before SHA、保護件数/保持を現在APIで照合。追加dispatch/rerunなし。
6. 許可されたread-only-smokeで待機受領/実Dashboard読取。同owner inputへ実executionと
   正式remaining-conditions観測を更新する必要がある。共有入力更新の唯一ownerとwriterとの
   競合制御が別途確立されない場合、ここで外部PATCHを止め、ローカル証拠を引渡す。
   snapshot/Gateを編集しない。人間手動更新を自動Workの実操作へ代入しない。
7. 外部更新が正式管理経路で行われた場合は同共有inputを正式writerで再読取し、改版/生成/
   同record投入/二度目のwriter再照合を実証する。コードfixture成功をこの結果へ代用しない。
8. 専用登録は正式停止操作の成功と、その後のenabled=false読戻しを別々に記録する。
   保存Prompt/対象も照合する。既存実行取消/担当枠解放/排他成立とは扱わない。
   共通dot、CI、正式同期は維持。Issue96/100は未実証管理を継続する。

停止出力はstatus、stage/reason、next_owner/action、保持証拠（event/work/claim/receipt、
現在試行と否定履歴、sync ZIP/report digest、予約journal）を残す。秘密は公開しない。
引渡し先はWork(root)/人間。止まった工程と不足資格・API・競合・不明結果をIssueへ要約し、
次操作は実記録のGET照合か正式ownerの手動読取承認。枠を削除して自動再送しない。

残る阻害条件は実Workの自動起動/受領、新環境のcontents-write資格、管理者によるref不変運用、
同共有入力外部更新の競合制御と既存実行のfencing。これらの未実証/保証不能をコードPASSで
覆わない。I-02 lease/監視、Phase2、新測定、I-07以降、空PRは開始しない。
