# V3.9 準備段階別確認（ローカル補助契約）

`startup_preparation.py --lifecycle <JSON>`を追加。実装前、merge前、merge後、終了の不足と次担当を別に出力する。既存v1のPREPARATION_COMPLETEは従来の5工程についての判定であり、全体成功ではない。新しいPHASE_EVIDENCE_COMPLETEも、その段階に必要な入力が揃ったという意味であり、正式Merge/Completion Gateではない。

```sh
python -B tools/startup_preparation.py \
  --input docs/startup-preparation-input.json \
  --state work/preparation/state.json --output work/preparation/generated \
  --lifecycle docs/preparation-lifecycle-example.json
```

例は合成・未登録。利用時は入力digest、Issue、実PR、owner、レビュー用ID、別の本担当再開ID、観測時刻と証拠を実値へ置換する。正本契約は`docs/schemas/preparation-lifecycle.schema.json`とPythonの厳密検証。未知field、role/scope/入力digest違い、ID流用、部分設定での確認済み主張を拒否する。JSON内のowner名は認証ではないため、正式共有recordへ直結してはならない。

| phase | 要求 | 要求しない未来の証拠 |
|---|---|---|
| PRE_IMPLEMENTATION | review実登録・保存設定確認 | 未確定PRの実受信・merge実行 |
| PRE_MERGE | review実PR受信、本担当実登録・保存設定、共有待機記録 | merge後Work・同期・次操作 |
| POST_MERGE | 本担当merge実受信・Work run・共有claim/receipt・同期・artifact・実次操作 | 登録だけによる起動推定 |
| FINISHED | 上記実結果と専用登録disabled読戻し・停止証拠 | 停止予定だけの完了 |

role=`review`と`owner_resume`は別ID。statusはNOT_ATTEMPTED/ATTEMPTING/REGISTERED/SETTINGS_CONFIRMED/FAILED/UNKNOWN/DISABLED_CONFIRMED。UNKNOWN/ATTEMPTINGは再送禁止の照合対象。保存設定の読戻しと実イベントは別フラグ。trigger=`pull_request_merged`は内部の正規化表現であり、Workにそのイベント名が存在すると主張しない。UIがclosedのみなら保存条件のmerged限定を正式UIで確認した後だけ正規化する。

生成物は従来6ファイルに加えてlifecycle-assessment.json、lifecycle-summary.md、owner_resume_registration.md。外部登録は送信しない。観測時刻だけで進捗を作らず、同一観測はNO_OP。新しい否定観測の後に古い成功を再投入できない。履歴は保存するが成功の代替にしない。入力版変更は新しいdigestへ明示再結合し、旧sidecarを保存したまま別outputを用いる。ローカル履歴は環境間排他や正式UNKNOWN ledgerではない。

このローカルsidecar自体の正式共有・Gate接続は対象外。別の明示v2契約を[preparation-evidence-v2.md](preparation-evidence-v2.md)で候補実装しており、main適用前は正式稼働ではない。I-07へ統合した追加実装は、段階別input/owner facts/schema移行、正式ownerによる同一共有input更新、collectorの現在PR/設定対応、trusted-main唯一writerの再照合、適用対象を限定したMerge Gate条件。I-01必要最小部分を先に適用し、汎用登録・適用自動化はその後に行う。ローカル補助判定を正式stateへコピーしない。

Hosted Windows・Work実登録・実受信・正式同期実ZIP取得はこのローカル検証では実施していない。

## V4.0: 工程別観測表示（Issue #130）

既存`--lifecycle`の`lifecycle-summary.md`と現在要約に、登録候補・各roleの登録/保存設定/実event/実起動/対象照合/停止、review結果投稿、owner待機受領、人間merge、Windows同期、結果保存の表を表示する。新しい証拠ファイルやfieldは追加せず、現在の同じassessmentから毎回再生成する。JSONの入力/schema/assessment/history、v2承認Prompt、登録資格、正式Gateは変更しない。`confirmed`は既存の明示的な**ローカル観測申告**のみ、`failed`は登録試行のFAILEDのみ、`unverified`は不足または既存契約で検証不能という意味であり、未実行・失敗の断定ではない。

実eventフラグはWork実起動を示さず、`work_run`文字列もrole付き実起動の認証ではない。現契約にはfull HEAD照合・本人結果投稿/GET・人間merge認証がないため、その工程は常に`unverified`。`sync_ref`/`artifact_ref`/`action_ref`だけでZIP検証・結果保存を成功にしない。既存sync verifierの実ZIP検証等は別の実証拠として扱う。`DISABLED_CONFIRMED`はローカルの停止読戻し申告であり、実際の正式updateと別peek、および処理中runの取消は区別する。UNKNOWNや有効状態を停止済みにしない。過去の肯定を現在の不足へ継承しない。

外部の実証結果・投稿失敗・停止失敗・取得不能の理由・証拠URLは、既存の同じ準備コメントのowner観測詳細へ集約し、本表へ二重保存しない。GETで投稿が存在する事実と、担当Work本人の投稿という根拠を分けて記す。実証用に未対応fieldを追加したり、表のconfirmedを正式Gateへ転用したりしない。候補生成は現CLI終了と対象/digestに一致する候補出力で別確認する。これはWork実行障害や配送・中断そのものの修正ではない。

## V4.0: 新規ownerの順次登録候補（Issue #128）

`--lifecycle`の`owner_resume_registration.md`は、既登録・登録試行履歴があるownerを`RECONCILE_ONLY`として保持する。新規ownerはreview先行とし、正常停止のsidecarだけでは`WAIT`。同じ実PR/full HEADの独立受入・必須CI・公開一致、正式停止update後の別peek falseをWork(root)が照合する。旧登録を取り消したり、再登録を指示したりしない。

候補を出すには、現在のPR/HEADを`--review-pr`と`--review-head`で明示し、任意の`--owner-registration-checks <JSON>`を加える（`--review-registration-request`との併用も可能）。このファイルは候補生成専用のローカル確認入力であり、既存input/state/lifecycleのschema、承認済みv2 Prompt、正式Gate/policy/保存データを変更しない。次は合成例であり、実証に転用しない。

```json
{
  "input_digest": "<current input digest>",
  "pr": 99,
  "head_sha": "<owner-verified current full HEAD>",
  "review_id": "<actual review automation ID>",
  "observed_at": "2026-10-08T03:00:00Z",
  "independent_review_accepted": true,
  "required_ci_passed": true,
  "publication_matched": true,
  "review_result_ref": "synthetic://result",
  "ci_ref": "synthetic://ci",
  "publication_ref": "synthetic://publication",
  "stop_update_ref": "synthetic://formal-update-response",
  "stop_peek_ref": "synthetic://separate-peek-response",
  "stop_update_at": "2026-10-08T02:58:00Z",
  "stop_peek_at": "2026-10-08T02:59:00Z",
  "stop_peek_enabled": false
}
```

`observed_at`は現在のsidecar観測と完全一致、PR/HEAD/input digest/review IDは現在対象と一致する必要がある。停止update→別peek→現在観測の時系列も照合する。UNKNOWN/未停止/未確認/古い観測/別HEAD/不足は`WAIT`。現在の否定を古い肯定で戻すことは既存lifecycle履歴検証で拒否する。候補はPRE_MERGE限定であり、登録不足を含むlifecycle判定自体は従来どおりWAITING/NOT_CERTIFIEDを保持する。

`CANDIDATE_ONLY`も実登録・サービス認証・自動完走ではない。JSONの真偽値や参照はWork(root)の照合申告であり、証拠原本の取得・独立性の認証を代行しない。実登録直前のGitHub対象/HEAD・重複・最新停止観測の再照合、正式登録、実ID/保存Prompt全文/取得可能設定/有効状態の別読戻しはWork(root)が行う。プログラムによる原子的な登録制御・実行配送分離・鮮度のサービス保証はない。review本人結果→停止/別peek false→owner登録の順を守り、人間merge後はowner本人の先行merge報告→既存正式同期実ZIP照合→関連検証→Gate対応範囲確認→本人結果保存/読戻し→専用停止/別peekを追跡する。
