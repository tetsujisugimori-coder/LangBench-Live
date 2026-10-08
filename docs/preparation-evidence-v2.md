# Issue #100: I-01段階別共有準備 v2

対象: https://github.com/tetsujisugimori-coder/LangBench-Live/issues/100 。
開始main: `82d4d0ab8212b4025610fc3d16a85b92176a907d`。
背景: https://github.com/tetsujisugimori-coder/LangBench-Live/issues/96 。
ユーザーの2026-10-08承認範囲の最小補修。V3.9添付の旧I-09/旧優先順位は今回指示で置換し、
I-01→I-07→I-03→I-06。Phase2、汎用lease、常設監視、新測定は起動しない。

## 契約と認証境界

既存 `startup_preparation.py` の入力/保存/生成処理、`preparation_github.py` の正式共有record、
既存collector/evaluatorへv2を明示接続する。既存 `work_owner_resume.py` はpurposeを拡張せず再利用する。
[JSON schema](schemas/preparation-evidence-v2.schema.json) とPythonの意味検証が契約。
policy top-levelもschema_version=2へ明示移行する。旧main updaterは2をtoken取得前に拒否するため、新条件を無視した旧PASSを生成できない。新readerはlegacy policy=1とpolicy=2を明示読解し、preparation_contract:2はpolicy=2でのみ許可する。Issue80/85/88/91/96のentry/条件/意味は保持する。

input/owner facts/state/request/snapshotはschema_version=2。共有markerは
`langbench-preparation-input:v2` / `langbench-preparation-snapshot:v2`。
未知field/marker、版混在、別owner/Issue/purpose/digest/PR/HEAD/role/IDは不足または停止。

v1は従来5工程と旧意味を維持。`PREPARATION_COMPLETE`、v2の`PHASE_EVIDENCE_COMPLETE`、
正式Merge/Completion PASS、I-01実動成功を別判定とする。ローカル`--lifecycle`はv1補助のみであり、
v2に混ぜることやsidecarのPASSを正式stateへコピーすることは拒否する。
明示移行はinput_versionを増やし、CLIでは`--migrate-v2`を付ける。共有移行では同commentのv2要求の
input_historyに旧入力をそのまま保持し、旧snapshotのprefixと照合する。旧snapshotからv2へ移行する
場合だけ一時的な版差を許可する。逆移行、履歴改変、未対応policy/readerは停止。
既存v1 operationsはv2 stateの`legacy.operations`に保持し、現在bindingを照合できる既存公開adapterだけが
解決する。新registration operationsと合わせて正式保存ledgerであり、旧UNKNOWNは削除しない。

GitHub RESTが返すcomment authorのlogin/id/typeをpolicy ownerと照合する。
owner factsのowner名や非空URL、settings_verified=trueだけでは認証しない。
Work正式UI/toolで保存設定を観測したownerによる申告を、Issue/purpose/input_version/digest/start SHAと
現在の実PR/full HEAD、別role/実ID、設定版/観測時刻へ結び付ける。
Workサービス内部の設定・イベント・runをGitHub tokenで直接認証する契約ではない。
非公開API、credential複製、GitHub ActionsからWorkを任意起動する機能は仮定しない。
JSONのdigestは改変検出/bindingであり署名やサービス認証ではない。

`registration_prompts`はrole別の承認済み**全文**/version/UTF-8 byte SHA256を保持する。
未取得はnullとして不足にする。実登録の詳細Promptを短いテンプレートに置換しない。
独立reviewの同HEAD確認、必要Ubuntu/Windows CI、禁止操作、結果引渡し等を含む実際の承認済み全文を
本担当が入力し、保存UIの全文と完全一致することを照合する。
設定版は保存設定変更時に増やし、新HEAD/input版には新しくbindingした観測が必要。
Prompt内のscopeと外側Triggerを別々に確認し、Promptだけで起動対象を認定しない。

## 段階ごとの不足

| phase | 必須 | 未来条件として要求しないもの |
|---|---|---|
| PRE_IMPLEMENTATION | Issue/owner/start SHA/仕様/必要条件、review実登録と保存設定、公開・回収、main policy/Dashboard | 未確定PRの実受信、owner_resume実ID、merge後証拠 |
| PR_BOUND | 現実PR/full HEAD、review番号binding、別owner_resume実登録/読戻し | review実受信、merge後実開始・sync・次操作 |
| PRE_MERGE | 上記、review実PR受信、独立した共有待機comment | 将来のmerge SHA、Work start/claim/receipt/sync |
| POST_MERGE | 実merge event/Work start、現在対象、共有claim後receipt、正式既存sync/実ZIP/digest/保持、実次操作 | 登録のみでの起動推定 |
| FINISHED | 上記結果、専用停止操作と両roleのenabled=false保存読戻し | 停止依頼・予定だけの完了 |

実PR前のreview外側scopeはrepository一致・pr=null・正確な`^Issue #100:` title_match。
実PR後は正しいPR番号・title_match=null。広いrepo全体scopeへ解除しない。
owner_resumeは別実IDでevents=[closed]/only_on_merge=trueを保存読戻しする。
reviewはonly_on_merge=false。opened/ready/closed、明示opt-in synchronize/review/commentの正式UI設定を
観測する。実イベントと保存設定は別record。未来merge SHAは入力へ作らない。

公式Merge Gateはpolicy `preparation_contract: 2` を持つ対象だけに追加する。今回の登録対象は#100。
現実PR/full HEAD・PRE_MERGE以降の現在準備と既存同HEAD CI/独立レビュー/metadata/ownershipを合わせる。
既存Issue80/85/88/91/96へ追加条件を一律適用しない。既merge時のMerge BLOCKED理由は再merge対象外であり、
Completion不足とは別。CompletionはPOST_MERGE以降のowner観測と既存sync/live smoke等を別に要求する。
専用停止はFINISHEDの準備条件で、正式Completionと別工程。

## CLIと同じ共有recordの更新

```sh
python -B tools/startup_preparation.py \
  --input docs/issue-100-preparation-input.json \
  --state work/issue100/state.json --output work/issue100/generated
```

このcandidate入力の実review IDは`6ac71f9572a48191bbf36c742b9e1720`。
実PR/HEAD/owner_resume ID/保存Prompt全文は未取得なのでnull。未確認を合成値で埋めない。
CLI生成物は案であり外部投稿/登録/受領/実動証拠ではない。
保存設定のowner factsを用意したら `--owner-facts work/issue100/owner-facts.json` を付ける。
公開repoのGETは `--github-read` でtokenなしでも利用できる。認証が必要な取得先は正規GH_TOKENの実行経路を使い、取得不能ならSTOPPED。POST/PATCHと正式writerはtoken必須を維持する。
v2 CLIは現在mainのpolicyを確認し、同Issue唯一の共有inputコメントをRESTの実author login/id/type、Issue/purpose、marker、input版/digest、policyで認証して取得する。指定local inputおよび任意の--owner-factsが共有inputと不一致ならSTOPPED。閲覧tokenの有無は投稿者認証を代替しない。local JSONの生成は未認証の案として保存できるが、正式phase/Gateへ採用しない。

認証取得後にAPIが失敗した場合はwriterと同じpreserve_negative_failure/resume(fetch_error=True)で否定履歴を保存する。local stateの肯定は正式読取へ移入せず、否定/conflictとUNKNOWN/ATTEMPTINGだけを禁止履歴として保持する。古い肯定の再読込では解除せず、新しい同bound正式観測が必要。
Ubuntu/Windows CI内のsubprocessはUTF-8/終了値/保存再読込の**合成回帰**でありlive CLI証拠ではない。

成功済みstateのledgerは生成requestへUNKNOWN/no external IDとして正規化し、writer専用成功を代筆しない。
同じinput履歴・未解決operationを含むowner領域だけを、同じ正式commentへ更新する。
writer snapshotと生成DashboardをWorkが直接編集しない。
唯一writerはtrusted-main `automation-dashboard.yml` の既存concurrencyの中で
同じ共有request/snapshotを再計算してPATCHし、その後collectorが現在準備を再計算する。
snapshotのPASSだけを読んでGateを成功させない。

UNKNOWN/ATTEMPTINGは照合対象で、登録再作成を許可しない。NOT_ATTEMPTED/REGISTERED/
SETTINGS_CONFIRMED/FAILED/DISABLED_CONFIRMEDを区別し、role-ID混同と旧PR転用を拒否。
入力変更後も否定watermarkと未解決ledgerを保存する。古い肯定二回、同時刻矛盾、混合snapshotの
新しい否定、API失敗でも、新否定とconflict barrierを落とさない。独立roleを全部検査してから不足判定する。
時刻だけの再観測はNO_OP。last_progress_at/last_observed_atを成功監視時刻や予定時刻へ読み替えない。
意味のあるinput/設定/否定/工程変更だけが進捗時刻を更新する。

コメント本文の無関係部分と人間追記はbyte保持。共有待機commentはwriter領域を含まない独立comment。
全UTF-8本文byte SHA256/実comment ID/full HEAD/approval参照/許可次操作/再開IDを固定する。
変更時は本担当が再受領する。二重収集、直前全文/updated_at再読込、書込後照合を維持する。
GitHub comment PATCH/claimもローカルlockも跨環境CAS/leaseではない。取得未確認なら新操作しない。
書込UNKNOWNは同commentを先に照合し、登録要求や同期dispatchを再送しない。

## merge前の実行準備とmerge後live smoke

本候補は開始mainに未適用の新契約を含む。未mergeコードを正式writer/self-hostedへ渡さず、
新Gateを正式PASSと称しない。旧#88/#91の限定導入例外も転用しない。
最新公開full HEAD Ubuntu/Windows CI、別Work同HEAD独立レビュー、実登録/保存設定/待機記録を揃えた
具体的候補に対して、本担当が必要な新限定前提受入を人間判断へ渡す。

1. 実PR確定後、本担当がreviewの外側PR bindingと詳細Promptを保存し正式UIで開き直す。
   別owner_resumeを実PR限定only_on_mergeで実登録し、実ID/enabled/Trigger/Prompt全文/設定版を読戻す。
   peekにTriggerが出ない場合は未確認のままにせず正式UIで確認する。取得不能ならmerge推奨不可。
2. 本担当が独立待機commentを保存し全byte digestと実IDを取得する。実HEAD変更後はCI/review/設定/待機bindingを更新。
   implementation_task receiptは再開claim/receiptと別。Issue100既存開始receiptの実run IDを再開runへ流用しない。
3. 人間merge後に、実event IDとWork実run/startを取得する。手動run_now/催促/PR99後付け登録は今回の実動証拠にしない。
   exact merge/current mainを再取得し、現在owner/dedup/共有claimを照合。排他未確認なら操作しない。
   claim後に固定した待機recordを実受領してreceiptを記録する。
4. 同期ownerは既存 `pull-local-main.yml`。既存run/attemptを読むだけでdispatch/rerunしない。
   pendingは同Work実行で継続確認し、継続不能時だけ正式pending限定再確認を登録/読戻す。
   job/step、exact before/after/target/merge/full HEAD、保護保持、単一sync-report実ZIPとAPI digest一致を取得し保持する。
   新測定NOT_REQUIREDは正式sync ZIPの免除ではない。手動介入は別記録。
5. mainに契約が反映された後、正規の公開GETまたは構成済み認証経路で実main CLIを実行する。
   `startup_preparation.py --github-read --owner-facts ...` と既存
   `work_owner_resume.py --handoff ... --state ... --github-read` の実終了値を保存する。
   本担当WorkではGH_TOKEN/GITHUB_TOKENが未設定で、開始main CLIはKeyError GH_TOKEN→exit1/STOPPEDを実観測済み。
   本補修は既存adapterの公開GETをtoken任意にし、本担当が正式公開APIのtokenなしGETで正mainを実取得できた経路を利用可能にする。
   正式pluginで実回収したZIPを `--sync-artifact-zip work/issue100/official-sync.zip` で既存CLIへ渡せる。
   現在APIのrun/attempt/name/id/expired=false/digestと提供bytesのSHA256、単一bounded inert reportを既存readerで照合する。
   未取得/過去ZIP/別attempt/改変/現在API不能はSTOPPED。fixture指定との併用は拒否する。
   main適用後のこのWork実CLI/live smokeはまだ未実証。公開GETが実行環境で成立しなければ不足を維持し、credential複製をしない。
6. 実開始/claim/receipt/同期/実次操作のowner領域を同じ正式共有input recordへ更新する。
   main唯一writerの再照合run/job/stepと同commentの現input_digest・不足/next_actionを読戻す。
   `WAITING`の古い不足が現在不足へ更新されたことを実証する。
   実再開CLIのcollectorは `include_preparation=False` でGitHub公開事実だけを収集する。
   その結果をv2 readerが評価するので、collector→準備Gate→再開collectorの自己参照を作らない。
7. 認証済みclaim/receiptの後、待機記録で許可された実live_smokeまたはsafe_stopを実行し証拠を保存する。safe_stopの実対応観測は保持するが、I-01成功一周へ代入しない。
   設定保存だけ、通知だけ、実次操作なし、同期/ZIP未確認ではI-01成功にしない。
   POST_MERGE/FINISHEDのI-01成功観測は実承認済みlive_smoke次操作と、その後の正式不足確認completion_observationを必要とする。正式Completionは既存契約対応CI/review/sync/live_smoke/FOLLOW_UP等の範囲のみ。準備完全と同義にしない。
8. 最終受領後、専用review/resumeだけを停止し、実停止操作とenabled=false読戻しをFINISHEDへ記録する。
   共通CI/sync/dotは維持する。I-01成立後も次テーマを自動起動しない。

接続状況は[接続図](i01-preparation-connection.md)、実装/実動の区別と改定は
[Log](automation-change-log.md)を参照。PR99の既存実sync/手動ZIP回収は背景証拠であり、今回の実動成功へ代入しない。
