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
| inert予約commit作成 | コード/branchを変更しないgit object。送信前にphase=commit/ATTEMPTINGを保存。結果不明ならrefを送らず停止し、commitも再送しない |
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

## 予約CLIの停止と通信復旧

予約CLIは既存 `startup_preparation.state_lock` のO_EXCLロック
`<state>.lock` を使う。同じstateの最初の読込・初期保存・現在facts確認・取得・送信前journal・
結果保存・例外時の診断追記（破損stateの別診断ファイルを含む）を一つのロック内で行う。
ロック取得失敗はstdoutへ停止理由を出すだけで、state・診断履歴・既存ロックを変更しない。
後発が古い空journalを保存して先行の不明送信履歴を消すことを防ぐ。これは同じローカル
ファイルを使う参加処理の保護であり、跨環境の担当排他はGitHub create-refによる別の保証。
ローカルロックを跨環境CAS/leaseへ昇格させない。

中断でロックが残る場合、自動削除・期限切れ・再送は行わない。人間がholderの終了、
stateの送信journalと診断履歴、実ref/commitを確認した後だけ手動解除する。stateと秘密を
保持したまま同じ引数で再開し、不明送信はGET照合だけにする。ロックを消すことは
GitHub担当枠の解除でも、未送信への変更でもない。

`--state` は `schema_version=1, kind=i01_reservation_state` の保存envelope。
`journal`（外部送信履歴）と追記型 `diagnostics`（工程・停止理由・次操作）を分離する。
最初のfacts取得前に明示的な `journal={}` をatomic保存し、以後診断だけで送信済みへ
昇格させない。journalが空であるという区別はこのenvelopeで明示した未送信履歴に限る。
ファイルの欠落を復旧手段にしない。外部送信後は同じstateと秘密を必ず保持する。

| 保存した状態 | 同じ引数・同じファイルで再実行したとき |
|---|---|
| 明示未送信journal + facts通信/対象/権限/待機の停止診断 | 現在factsを二度再取得し、対象・policy・承認・待機・秘密を再確認。条件成立時だけ予約へ進む。過去の診断を残す |
| phase=commit、ATTEMPTING、commit_sha=null | commit送信結果は不明。実ref/commitのGET照合経路だけを使用し、commit/ref POSTを増やさず停止。SHA不明のcommitを推測して代入しない |
| phase=ref、ATTEMPTING/UNKNOWN、有効commit SHA | 送信直前記録。送ったか不明な途中停止も含む。実ref/commitをGETし、保存binding/SHAと一致した場合だけACQUIRED。存在未確認/通信失敗なら保持して停止し、再送しない |
| ACQUIRED | 現在factsと秘密を再確認し、実ref/commitをGET再照合。別担当/異なるbinding/SHAなら競合・改変として停止。過去の取得記録は消さない |
| 破損・不完全・矛盾したjournal、旧形式の停止診断だけ | 未送信と推定しない。元ファイルをbyte単位で保持し、別の `<state>.diagnostics.json` へ停止履歴を追記。人間による実記録照合が必要 |

完全な旧ATTEMPTING/UNKNOWN/ACQUIREDはbinding/ref/commit SHAを検証して移行し、
既存diagnosticも保持する。送信履歴が欠落した旧停止記録は自動移行できない。
tokenの未設定・空値など確実にローカル判定できる書込前条件は、送信中journalを
保存する前に確認する。輸送層でも同じtoken検査を維持する。tokenがあるだけでは
contents-write権限の実証にならず、資格確認用の試験POSTは行わない。未設定で止まった
新規未送信stateは診断を残し、token設定後に現在factsを二度再取得して予約へ進める。
既存phase=commit/refの不明記録を「以前token不足だったはず」と推測して空へ戻さない。
各実POSTの前にはdurable journal保存を必須とし、保存失敗時は対応するPOSTを送らない。commit作成後・ref送信前の保存失敗は
最後のdurable phase=commitを保持して停止する。診断保存も失敗した場合はstdoutへ
`diagnostic_save_failed` を出し、元stateと秘密を保持して引渡す。

復旧は停止した工程・理由を確認して通信/現在条件を直し、上記予約CLIを同じ引数で再実行する。
未送信の停止を含め全診断は取得成功後も残る。結果不明・競合・秘密不一致・破損ならstateを
削除/空にして取得し直さず、正式ownerへ元state、handoff、実ref/commit GET結果と不足条件を
引渡す。秘密そのものは公開しない。人間の読取引受は既存の別承認経路を使用し、担当枠を
解除・譲渡しない。これはローカル送信記録の復旧であり、跨環境leaseではない。

2026-10-08の本担当準備では、Issue102/PR103専用の別review/owner_resumeを正式toolで登録した。
review実IDは `6ac79f38824c8191be0e9b4b08e1b5f0`、owner_resume実IDは
`6ac79f46e5b08191bcd84e9d6cbedef3`。repository/PR103/authorの限定条件で、reviewは
opened/ready/closed/synchronize、owner_resumeはmerge-onlyを登録要求した。別peekで
保存Prompt全文の一致と両enabled=trueを観測したが、peekは外側Triggerを返さない。
要求条件と保存済み条件の読戻しを区別し、現在はREGISTEREDでありSETTINGS_CONFIRMEDではない。
正式共有input/独立待機commentの公開、新Work実行環境のcontents-write資格、外部更新の
競合制御は未確認。登録成功、実起動、待機受領、fixture成功を別証拠として扱う。
PR103は最終HEAD独立再レビューとmerge前準備の確認までdraftを維持する。

## Issue102の限定scope接続

Issue102のpurposeは `work-owner-resume-i01-repair` のまま保持する。v2 input/owner facts/
request/handoffのschemaとPython validatorはこのpurposeをIssue102だけで受け付け、
policy生成は同scopeにresume_protocol=2を付ける。v1 handoffには追加しない。
dedup/予約bindingは実inputのpurposeを含め、旧Issue100の担当枠・入力・待機を転用しない。
候補policyは実review IDを持つ102 entryだけ追加し、既存entryを変更しない。
候補main適用や登録を正式準備/Gate/I-01成功と扱わない。

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
   本PRのpolicy変更は100の読取契約補修と、実専用review IDを持つ102の限定追加。
   現toolはGitHub webhook登録を公開しており両roleの登録操作は成功したが、外側保存条件は
   peekで取得不能。正式UI/toolで保存条件を確認し、正式policyと共有inputの対象を
   整えるまで102の実証を停止する。候補コードレビューとこの運用準備不足は別評価する。
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

## Issue102 management route (PR103)

Only Issue102 / PR103 / `work-owner-resume-i01-repair` opts into
`i01_manager` and `manual_review` policy extensions. Other Issues and the
original automatic/private capability and manual read-only routes retain their
contracts. Main deployment plus the human-approved scope authorizes this
limited manager; the earlier fixed waiting record is not a blanket write permit.

The existing GitHub connection publishes a whole `langbench-i01-request:v1`
comment to Issue102. `tools/i01_management.py` builds it locally and reads its
response using public GETs. A saved request is immutable: reuse the same body and
request ID after uncertain submission, find the canonical first comment, and do
not generate a new nonce or edit/delete requests. Never put a PAT, GH_TOKEN,
private capability, signing key, or bearer secret in the request or an Issue.
The public nonce is an identifier, not a secret or proof of possession.

The trusted-main `manage-i01` job in `automation-dashboard.yml` uses only its
job-scoped `GITHUB_TOKEN`. Its `contents:write` permission is isolated from the
ordinary observer. Both jobs run inside the existing repository concurrency
group; the observer runs after the manager even if management stops. PR head,
artifact code, shell supplied in comments, arbitrary refs and arbitrary Git
payloads are never executed. Manager writes are only the bound one-shot
commit/ref POST and append-only Issue102 journals/amendments. No dispatch,
measurement, cancellation, ref modification/deletion, merge or close is added.
GitHub/App account authentication is the trust root. A shared account cannot
cryptographically distinguish two Work executions or the independent reviewer
from the implementation owner. `run_id=null`, route `managed`, and assurance
`github_actor_not_service_run` preserve that limitation instead of claiming a
service run or private capability possession.

### Reservation and crash recovery

A reservation request binds the current input version/digest, actual merge,
reviewed full HEAD, waiting bytes, declared event/start, resume registration,
public execution ID and read-only authorization. The manager authenticates
GitHub comment ID/issue/author/type and immutable timestamps, reads current main
policy and public facts twice, and uses the same owner-resume preflight as the
original CLI. Before Git commit POST it publishes and GET-confirms a bot-owned
`langbench-i01-journal:v1` commit-stage record. Before ref POST it persists the
known commit SHA in a ref-stage record. No ephemeral Actions filesystem is used
as cross-run journal authority. A successful ref is GET-checked against the
entire binding and parent before an acquired journal is published.

A commit journal without a known commit result never sends again. A ref journal
only GET-reconciles the permanent ref; absent, changed or conflicting results
stop. Another request's retained journal for the same operation also fences a
new attempt even while the ref is absent. Identical duplicate request bodies
use the first GitHub comment ID; differing payloads with the same request ID
stop. Duplicate or edited journals stop. No expiry, takeover or automatic reset
exists. Repo administrators are the trust root: journal/request/amendment and
reservation-ref deletion or rewriting is prohibited operationally; the code
does not claim to prevent an administrator from erasing GitHub history.

### Shared input updates

The pinned owner base comment6067589610 remains the sole normal preparation
input marker. Its whole request JSON is pinned by `base_record_digest`; the
fixed waiting comment6067573923 remains unchanged. The manager appends
`langbench-i01-amendment:v1` records binding a canonical authenticated update
request and the entire previous record digest. A single nonbranching chain
produces one logical current input, with consecutive input versions and complete
input/intent history. The original author is never impersonated or replaced.
A separate unique bot-owned `langbench-i01-managed-snapshot:v1` comment holds the
writer's preparation snapshot; the base is not PATCHed in this route.

Updates specify `expected_input_version` and `expected_input_digest`; same-base
competing requests stop before publication. Immutable scope, PR, owner,
registrations, requirements, actors and starting main are not editable through
this route. Only input version, phase, observed HEAD, approved prompt
expectations and explicit bound owner observations can advance, and phases do
not regress. The proposed HEAD must equal the actual PR HEAD. Execution-bearing
owner updates require the exact authenticated managed request and permanent
reservation and cannot switch or erase an existing execution. Observations do
not grant PASS themselves: the sole writer revalidates current GitHub facts,
real ZIP/sync, negative histories and executed read-only operation.

Concurrency serializes the cooperating manager and writer, not every GitHub
administrator. The inbox is scanned on each existing event because pending runs
may coalesce. Version/digest chains, immutable records and pre/post readback
detect outside edits; they are not a GitHub comment CAS or cross-service lease.
Uncertainty stops and retains evidence. Bot output is processed in the same run;
it is not assumed to start another Actions run. Existing connection events and
effective token/ruleset permissions require real post-merge confirmation.

### Independent manual review

The approved new independent actor is `/root/pr103_independent_review`, with the
original delegation record review5475171001. Its own new PR **review** may contain
a whole `langbench-manual-work-review:v1` JSON envelope, as specified by
`docs/schemas/i01-management-v1.schema.json`. The payload binds repo/Issue/PR,
full HEAD, actor, delegation, verdict, blockers, follow-up and conditions. The
collector authenticates actual GitHub author ID/type, review state, review ID,
submission time and `commit_id`, and the same evaluator is used by Dashboard
and owner resume. General prose, implementation-owner handoff comments and an
old-head result do not become a current PASS. COMMENTED is kept COMMENTED;
manual_handoff is not the old review automation or an authenticated Work run.
Dismissal, malformed trusted evidence or changes-requested/PASS contradiction
fail closed. Existing automation comments continue to use their original schema.

A final new HEAD requires the independent actor's own new record and new hosted
CI. The review ID is external evidence, not a new constant committed into the
same HEAD; this avoids a review-ID/HEAD cycle. The original dispatch receipt and
other Merge/Completion prerequisites remain required and are not bypassed by
this extension. If the direct manual implementation has no supported initial
receipt, Dashboard still reports that separate blocker rather than fabricating
one. Likewise, hidden automation trigger values remain unconfirmed.

### Work procedure and checks

1. Read the main policy and the sole base plus amendments. Save the logical
   request JSON as `preparation-record.json` and an unclaimed v2 event/start
   handoff as `handoff.json`. Actual observed data is required, not these names
   or fixtures as proof.
2. Build an inert reservation submission (no network mutation):
   `python -B tools/i01_management.py --preparation-record preparation-record.json --reserve-handoff handoff.json --output request.md`.
   Publish the saved whole envelope once through the supported GitHub connection.
3. Read the canonical receipt without write credentials:
   `python -B tools/i01_management.py --read-response <actual-comment-id> --output response.json`.
   Only ACQUIRED contains a verified handoff/claim. PENDING/UNKNOWN is not a
   resend permit. Save the returned handoff separately for the existing
   `work_owner_resume.py --github-read --read-only-smoke` procedure. The managed
   route needs no `--capability-file` and claims no secret possession.
4. Prepare the next version's owner observations, complete history and unchanged
   intent ledger; build an update with `--preparation-record <current-record>
   --update-record <next-record> --output update.md`. Publish it through the same
   connection, read its APPLIED response and verify the sole writer twice.
5. Stop the dedicated existing automation through the supported official
   update/peek or UI management path after receiving final results; no new
   automation-stop API or common-workflow disable is introduced here.

Pre-merge acceptance is code/schema/contract checks, hosted Ubuntu/Windows CI
and the final independent same-HEAD record. Real merge/event/start, connection
`issue_comment` delivery, effective token write permission, permanent reservation,
actual smoke receipt, managed update/two writer reads and dedicated automation
stop remain post-merge evidence. Fixtures never certify I-01 COMPLETE. No secret
setting is requested of the user. If repository policy blocks the manager, check
GitHub Settings → Actions → General and Settings → Rules → Rulesets for the
reserved tag namespace; report the exact denied operation before changing policy.
