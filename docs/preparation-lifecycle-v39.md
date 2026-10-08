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
