# Issue #68 PR-A: Windows 最適化解析の実行準備

この段階では Windows 実機解析も性能本測定も実行しない。既存の公開解析、PR #67 の
`issue66-balanced-final-01`、測定コード SHA
`fde3f78b385034248bac9dfe7a97c8da37ffb3ae`、raw/results/data は変更しない。

## PR-A マージ後の再現手順

1. PR-A を人間がマージし、`Pull local main after verified merge` が成功して、対象 SHA と
   Windows 作業コピーの保護データ保持を確認する。
2. default branch の `Prepare Windows function-call analysis artifact` は同期 workflow の成功完了を
   `workflow_run` で受ける。PR branch からの手動 dispatch は設けない。解析 ID は同期 run ID から一意に決める。
3. `authorize` が PR #69 の merged/base/head repository と Issue #68/PR-A 本文参照、固定 main SHA、
   同期 run の ID/path/repository/name/event/branch/SHA/status を GitHub API で再照合する。
   不一致なら実機 job を起動しない。
4. 実機 job は専用四 label の runner で固定 SHA を checkout し、`RUNNER_TEMP` の未使用先へ
   C/Python/JavaScript 解析を生成する。開始前に同期・測定と共有する Git common-directory lock と
   function-call measurement lock を、信頼済み固定設定のユーザー作業コピーから取得する。その repository root、
   origin、main、固定 SHA、tracked 状態を確認し、競合時は出力作成前に停止する。実行コードと出力はそれぞれ
   固定 SHA の runner checkout と `RUNNER_TEMP` に置き、ユーザー作業フォルダーの成果物は上書きしない。
5. 生成直後から `run-state.json` を atomic 更新し、stage ごとの sanitized command、exit code、
   stdout/stderr log、source/condition/evidence hash を残す。validator の結果を `validation.json` に保存する。
   成否を問わず raw package は runner の一時領域に残し、upload 前に別の検査済み bundle を作る。
   秘密情報や絶対 path を含む原本は bundle に入れず、text は該当箇所のみ伏字にして
   安全な state/log/先行 trace と失敗原因を保持する。安全化できない file は除外する。
   最終 bundle 全体の scan に成功した場合だけ 14 日 artifact として upload する。

JavaScript は通常 benchmark entry point を trace flags 付きで起動せず、専用 harness が時間計測・sample
集計・result JSON 保存を行わずに対象関数だけを両順序で刺激する。C/Python は静的根拠のため順序独立、
JavaScript は trace で実際に観測した順序だけを `confirmed` とし、それ以外は `unconfirmed` として残す。
順序ごとの stdout/stderr/exit code は各 trace file へ直ちに保存し、findings・実コマンド・刺激条件・根拠 hash
も順序別に記録する。途中失敗では先行 trace を保持するが manifest/provenance を完成させず、成功扱いしない。

artifact は未公開の検査対象であり、それだけで Windows 実機成果物の公開、解析判定の更新、
PR #67 条件との一致、または最適化の因果効果を意味しない。内容とローカル path/秘密情報を検査し、
現行 source hash・処理系・起動条件・対象関数の根拠を照合した後、別の PR-B でのみ公開する。

Cloud Linux と GitHub-hosted Windows で作る fixture は経路の回帰確認専用であり、実機解析成果物として扱わない。
