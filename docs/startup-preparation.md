# Issue #88 開始準備の組み立て・進捗管理

仕様正本: https://github.com/tetsujisugimori-coder/LangBench-Live/issues/88 の本文全文。
開始 main: `5eda8bbf5be8433b2f3909c4e7a17a0cd13b9aef`。
本担当・implementation/fix dispatch owner は Work(root)。実装と独立レビューは別実行。

## 使用例と入力・出力

```sh
python -B tools/startup_preparation.py \
  --input docs/startup-preparation-input.json \
  --state work/issue88/state.json --output work/issue88/generated
```

Work(root) が非公開 API ではなく実画面・実イベントから確認した結果は、別 JSON を
`--owner-facts <path>` で渡す。record は repository/Issue/purpose/formal owner/input version/
input digest/start SHA/観測時刻/確認担当 Work(root) に結び付け、review の登録 ID・enabled・対象 event・実 event・
照合結果・証拠参照と、publication の正式担当・主経路・回収経路・証拠参照を保持する。
取得不能は `available=false`（結果欄は null）として UNKNOWN、入力なしは UNCONFIRMED なので
両者を混同しない。この入力は準備証拠だけで、Work PASS や dispatch receipt を生成しない。
直接スクリプト実行とパッケージ実行の両方で、owner facts を保存状態・現在要約・共有用
record に反映する。`--github-read` 併用時は公開情報と同じ再開処理へ渡す。非併用時は
owner の確認対象だけを反映し、Issue/policy/Dashboard を確認済みにはしない。
登録済みで実イベント未確認なら `event_verified=false, actual_event=null` として待機できる。
`owner_observations` は現在入力のdigestとreview/publicationの最後の認証観測時刻を保持する。
入力なし・取得不能でもこの履歴を消さず、古い肯定結果による巻戻しを拒否する。
入力版/SHAの変更ではbindingを失効させ、新入力に結び付いた証拠を要求する。
旧v1 cache/snapshotにこの欄がない場合は残存stage証拠から観測時刻を引継ぐ。
JSON・生成ファイル・CLI標準出力はUTF-8。Windowsで出力を取り込む場合もUTF-8として読む。

入力 Issue は未取得時 null、取得後は実正整数 ID。purpose は入力目的の識別子。
#88/purpose は本PR自身の設定・実例であり、ツールの入力制約ではない。repository は現対象固定。
JSON schema は `docs/schemas/startup-preparation-input.schema.json`。CLI は追加依存なしで
同じ必須フィールド・型・範囲と非空根拠を検証する。例の ID は実登録 ID、受入テストは
すべて合成 fixture。入力例は登録・enabled・実イベント・公開・実装開始を認定しない。

| 入力 | 出力 |
|---|---|
| repository / Issue / purpose / specification / start_main_sha | `issue_body.md` と全状態のスコープ |
| owner / work_author / actors | 本文案・policy の正式 identity、dispatch/review/sync owner |
| requirements / requirement_reasons | 本文案の入力全文・policy差分・保存状態。欠損はエラー |
| work_automation_id | `review_registration.md`。未取得は null、policy生成は待機 |
| 全入力・input_version | 決定的 SHA-256、`preparation.json`、`github_record.md` |
| 工程・証拠・確認対象・観測時刻・待機理由・next_owner/action | `summary.md` と保存 state |
| 現policy | `policy_diff.json`（追加だけ。同一登録は空差分、矛盾は拒否） |

既定は外部書込・起動なし。承認参照だけで承認認定しない。IDs、run、RUNNING、PASS を
生成しない。Work 非公開 API は呼ばない。requirements の NOT_REQUIRED は明示入力のみ。
Issue ID またはレビュー ID 未取得時も他の案と現在要約は生成できる。

## 保存・中断・再開

state は Gate 機械 state v1 と別の `kind=startup_preparation`。一時ファイルへの書込、flush /
fsync、同 directory の os.replace で原子保存する。CLI は state lock を O_EXCL で取得し、
競合は停止。異常終了の lock は自動回収しない。本担当が稼働と unknown ledger を確認して
手動解除する。破損 state / 重複 JSON key / 非有限値 / 不明 schema は置換しない。

取得前の外部 ID は null。`--mark-unknown policy_pr` などは、本担当が明示要求を外部へ
渡す**前**に成否不明 intent を保存するための操作であり、送信機能ではない。同 key は
再登録できない。SHA/入力版変更後も同 action の UNKNOWN があれば再送禁止。確認済みも
同 key 再送禁止。UNKNOWN は公開 GitHub の現在 ID が一意に一致するか、本担当による
未実装 Work 側の外部照合が必要。該当 task を取得できない場合は unknown を残す。

```sh
# 必要な場合に限る読み取り。GitHub REST 接続と有効な GH_TOKEN が必要。
python -B tools/startup_preparation.py \
  --input docs/startup-preparation-input.json \
  --state work/issue88/state.json --output work/issue88/generated --github-read
```

read adapter は現在の Issue purpose/owner、linked PR、main full SHA を読取り、**その SHA** の
policy を取得する。PR merged と main policy 読戻しは別工程。取得失敗は例外・非0終了。
過去の取得成功を今回の成功にしない。再開では新事実から各工程を再構成し、欠損した証拠を
確認済みのまま残さない。同じ事実の再観測は NO_OP で進捗・更新時刻を変更しない。
`--github-read` は保存済み UNKNOWN operation も現在の input digest/scope に対して照合する。
一意な linked PR/正式 receipt だけ CONFIRMED とし、取得失敗・複数候補は UNKNOWN のまま
停止する。読取再開から書込・再送・dispatch は行わない。

input_version を増やして変更する。仕様/担当/owner/SHA/requirements の変更は依存する
工程だけ INVALIDATED。operations ledger は保持する。版だけ同じで値を変える、旧版へ
戻す、担当が異なる evidence、別 Issue/purpose/owner は拒否。
正式 record は同じ repository/purpose/owner に限定した昇順の `input_history` も保持し、各
operation の digest/key を当時入力へ照合する。これにより Issue=null から実 Issue、版/SHA
変更後も UNKNOWN を削除せず初回共有でき、既存 snapshot の更新にも同じ検証を適用する。
既存snapshotの履歴と現在入力を改変不可のprefixとして照合し、未共有の中間版を順に
rebaseする。v1共有後にローカルだけでv2→v3へ変更しても同じ記録を再開できる。
保存済みUNKNOWN ledgerの削除は拒否し、入力移行後も未解決操作を保持する。
履歴のない旧 key、実 Issue から別 Issue への移動、無関係 purpose/owner、順序逆転は拒否する。
ローカル保存は環境間共有済みとは表示しない。runtimeごとの自動 commit はしない。

## 正式 GitHub 保存と唯一 writer

1. CLI は owner が確認する `github_record.md` の**案**を生成する。
2. policy が人間 merge され trusted main で読戻された後、Work(root) が正式 owner として
   入力対象の実 Issue に明示入力 record を一度保存する。新 task は作らない。送信成否不明なら
   コメント一覧から同 record を照合し、POST を繰り返さない。
3. 以後はその同じコメントの input record を owner が更新する。人間の追記は可能。
4. 既存 `tools/update_automation_dashboard.py` が既存 workflow の trusted-main checkout と
   repository concurrency の中で `reconcile_preparation()` を呼ぶ。writer は POST せず、
   正式 owner 入力コメントの専用 snapshot 領域だけ PATCH する。他 writer は導入しない。
5. 既存 workflow に届く Issue comment event が再照合のヒントになる。event の内容/日時を
   進捗認定に使わず、毎回現在 REST 状態を再取得する。同期 workflow は変更しない。

形式は `langbench-preparation-input:v1` と `langbench-preparation-snapshot:v1`。
既存 `langbench-automation-state:v1` と別。正式入力は schema/kind、repository、Issue、
purpose、owner(login/id/type)、input_version、canonical input_digest、全文入力、検証済み入力履歴、
owner facts、unknown operations を持つ。comment author の正式 owner と policy の owner/work_author/automation/
requirements/dispatch owner に一致しない record は取り込まない。snapshot は input版/digest、
元 request digest、comment ID、状態全文を保存する。既存 Gate 証拠/receipt を読み替えない。

writer は record 一件だけを許可し、複数は競合停止。最新版 state から旧 input版を拒否し、
操作 input binding 変更も拒否。owner は snapshot を編集せず入力だけ更新する。
GitHub comment PATCH は CAS を提供しない。既存 serialization、現在事実の二重収集、書込直前の
コメント全文再取得、書込後の全文と外部事実照合を行う。検出した事前競合は無書込。
一覧取得・単体取得・PATCH応答・事後読戻しの各段階で、正整数comment ID、対象Issue URL、
正式ownerの実identity、要求recordと既存snapshotを認証する。本文全体は空白も含め正確に
比較し、`performed_via_github_app`などの不要な付帯情報は比較しない。必要field欠損・型不正は停止。
`updated_at`は有効な日時であることを確認する補助情報で、本文の指紋には使わない。
事前取得間で日時だけが変わった場合も、本文を戻した編集の可能性があるため無書込で停止し、
次の呼出しで最新本文・日時から再照合する。同じ本文から過去の編集不存在を断定しない。
更新は確認した最新本文のwriter領域だけに行い、PATCH応答と事後読戻しの期待本文も確認する。
事後競合/書込応答不明は UNKNOWN として非成功、同呼出し内の再送なし。以後の event は
保存済み record と現在事実を再取得し、同一なら NO_OP にして再送しない。最終読取後の
極小 race は排除不能。表示 state はキャッシュであり、成功/dispatch/Gate の権威ではない。
期限タイマーがないため事後 event の到着・再照合の期限保証不能。

人間追記・無関係本文・owner入力・他コメントは byte 保持する。NO_OP は更新時刻も保持。
準備取込み失敗はプロセス非0と準備エラーを返すが、それだけを理由に Gate safe_stop は
呼ばない。既存 Gate は独立に現在の既存証拠を評価する。同期 artifact digest 検証は既存
`GitHub.sync_report()` のまま必須で、measurement NOT_REQUIRED から免除しない。

## 現在要約・状態と未実装接続

工程は Issue 未確認/確認済、review 未登録または未確認/取得不能/登録 enabled/実イベント未確認、
policy案/PR公開/人間merge待ち/merge済main読戻し待ち/main確認済、正式Dashboard未適用/
対応確認済、公開経路未確認/確認済を evidence と reason で区別する。
`PREPARATION_COMPLETE`、AUTOMATION_ARMED、実装開始、Merge、Completion PASS は別。

public GitHub 読取のみで publication 書込権限は認定しない。Work登録/実イベントの自動取得、
Cloud全task一覧/起動/送信、正式同期の開始、期限・次owner自動起動は未実装。
このため CLI / 正式 record だけで独立 Work 完了や準備完了を偽認定しない。Python の純粋
`resume()` は adapter の現在 facts を使うが、合成 fixture の complete は実結果ではない。
正式Dashboardの reference は現policyと機械 state のスコープ確認後だけ表示する。next owner/action
は未完了工程の権限で決め、review・policy 公開・Dashboard は Work(root)、publication 経路は
正式公開担当、公開済み policy PR は人間 merge、全準備確認後だけ実装担当を表示する。
policy が未適用なら Dashboard 確認より policy 公開・人間 merge・main 読戻しを優先する。
既に merge 済みなのに main 適用未確認の場合の次担当は Work(root) であり、人間へ再mergeを求めない。
機械Merge Gate未認定・Completion未認定・期限保証不能を表示する。

## Issue本文の全受入項目と検証対応

| 仕様群 | 実装と検証 |
|---|---|
| A: schema、一入力から全案、担当・必要条件と理由、ID null、既定無書込 | InputGeneration、CLI end-to-end。policy差分は初期 receipt null |
| B: 工程/証拠/確認対象/時刻/待機/next、原子保存、破損fail-closed、決定性 | StateResume（roundtrip、replace失敗保持、破損、determinism） |
| B: 中断dedup、成否不明再送禁止、外部照合、入力/担当/SHA変更時限定失効 | unknown intent→保存→再開→一意ID照合、旧UNKNOWN保持、影響依存表 |
| C: 今どこ/待ち/誰/次、DashboardとGate適用範囲、ARMED/実装/各PASS分離 | summary、enabled≠real event、merged PR≠main読戻し、Gate分離 |
| C: 明示新record、唯一trusted-main writer、repo/Issue/purpose/owner/入力版認証 | GithubTransport の real adapter + fake REST、他Issue/owner/版/digest拒否 |
| C: 同記録更新、人間追記/無関係本文/既存証拠保持、競合/古event/NO_OP | 同ID PATCH、古input拒否、double-read edit競合、unknown write restart NO_OP |
| C: 準備失敗とGate証拠分離、PASS/receiptを生成しない | 準備writerと既存Gate別try、既存parser/evaluator/receipt回帰 |
| D: 現policy形式、initial_dispatch:null、既存80/85不変、矛盾拒否 | policy equality / base snapshot、矛盾登録、初期 state roundtrip |
| 必須: 破損/取得失敗を成功にしない | 壊れたlocal/schema、REST失敗、競合/unknown 非成功 |
| 必須: 初回implementation FAILED/CANCELLEDをreview/syncが隠さない | 両状態×両後続actionの Gate BLOCKED 回帰、既存85 retry回帰 |
| 必須: 既存parser/Gate/receipt/writer/dedup/同期安全 | 全Python discovery、Node回帰、Hosted Windows既存必須suite |
| 必須: 最新公開full HEAD Hosted Ubuntu/Windows CI、独立コード・設定レビュー | PR公開後、CI実結果と別Work実結果を本担当が別々に確認 |
| merge後: policy/writer/tool main読戻し、exact merge同期証拠/digest、最小実Issue smoke | 人間merge後の本担当作業。今回fixture結果では認定しない |

## 禁止範囲と本PR限定導入

未マージ self-hosted・新測定・保存済み測定データ編集・同期workflow変更・dot設定・
次担当自動起動・期限タイマー・本担当再発火・自動回収・専用Web Dashboard・汎用engineは
追加しない。#83再開、#85 CLI起動、#86未完了処理取込み、他Issue起動はしない。
Work非公開API、手動PASS/独立PASS代筆、dispatch receipt捏造、自動merge/Gate緩和は禁止。

今回 #88 policy は開始main未登録。本PRだけ、最新公開full HEADの Hosted Ubuntu/Windows CI、
別実行の独立コード・設定レビュー、既存Dashboard/Gate/receipt回帰、人間最終mergeによる
限定初回導入。**機械Merge Gate未認定**。通常/将来Issueへ一般化しない。
人間 merge 待ちで止める。Completionを準備完了で代用しない。


## V3.9段階別補助確認

追加の--lifecycle入力と境界は[preparation-lifecycle-v39.md](preparation-lifecycle-v39.md)を参照。旧v1とローカル補助判定は正式Gate・I-01全体成功を表さない。正式v2契約は[preparation-evidence-v2.md](preparation-evidence-v2.md)を参照。
