# Issue #68 PR-A: Windows 最適化解析の実行準備

この段階では Windows 実機解析も性能本測定も実行しない。既存の公開解析、PR #67 の
`issue66-balanced-final-01`、測定コード SHA
`fde3f78b385034248bac9dfe7a97c8da37ffb3ae`、raw/results/data は変更しない。

## PR-A マージ後の再現手順

1. PR-A を人間がマージし、`Pull local main after verified merge` が成功して、対象 SHA と
   Windows 作業コピーの保護データ保持を確認する。
2. Actions の `Prepare Windows function-call analysis artifact` を一度だけ手動起動する。
   `merged_pr_number` はマージ済み PR-A、`sync_run_id` は同じ SHA の成功した同期 run、
   `analysis_id` は新規の Issue #68 専用 ID とする。任意 ref や shell command は入力できない。
3. `authorize` が PR の base/repository、merge 状態、最新 main の固定 SHA、同期 workflow の
   name/event/branch/SHA/status に加え、Issue #68 と PR-A の本文参照を GitHub API で照合する。
   workflow 自体も `refs/heads/main` からの dispatch に限定し、照合失敗時は実機 job を起動しない。
4. 実機 job は専用四 label の runner で固定 SHA を checkout し、`RUNNER_TEMP` の未使用先へ
   C/Python/JavaScript 解析を生成する。開始前に同期・測定と共有する Git common-directory lock と
   function-call measurement lock を、信頼済み固定設定のユーザー作業コピーから取得する。その repository root、
   origin、main、固定 SHA、tracked 状態を確認し、競合時は出力作成前に停止する。実行コードと出力はそれぞれ
   固定 SHA の runner checkout と `RUNNER_TEMP` に置き、ユーザー作業フォルダーの成果物は上書きしない。
5. validator が manifest、解析 SHA、両測定順序の適用範囲、trace と本測定の分離、および全根拠
   SHA-256 を検証する。失敗時を含め、生成できた package は 14 日 artifact として保持する。

JavaScript は通常 benchmark entry point を trace flags 付きで起動せず、専用 harness が時間計測・sample
集計・result JSON 保存を行わずに対象関数だけを両順序で刺激する。C/Python は静的根拠のため順序独立、
JavaScript は trace で実際に観測した順序だけを `confirmed` とし、それ以外は `unconfirmed` として残す。
順序ごとの stdout/stderr/exit code は各 trace file へ直ちに保存し、findings・実コマンド・刺激条件・根拠 hash
も順序別に記録する。途中失敗では先行 trace を保持するが manifest/provenance を完成させず、成功扱いしない。

artifact は未公開の検査対象であり、それだけで Windows 実機成果物の公開、解析判定の更新、
PR #67 条件との一致、または最適化の因果効果を意味しない。内容とローカル path/秘密情報を検査し、
現行 source hash・処理系・起動条件・対象関数の根拠を照合した後、別の PR-B でのみ公開する。

Cloud Linux と GitHub-hosted Windows で作る fixture は経路の回帰確認専用であり、実機解析成果物として扱わない。
