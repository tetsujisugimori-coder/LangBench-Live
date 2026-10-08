# 自動化接続の改定Log

## 2026-10-08 / Issue #100 / I-01最小準備補修

変更前: PR99の既存再開CLIは実装済みだが、v1開始準備は段階別共有設定観測を扱わず、
本担当再開登録不足はMerge Gateに未接続。添付キットの--lifecycleはローカル補助契約。

変更後: 明示v2 input/owner facts/shared marker/state、保存Prompt全文/版/digest、実PR/HEAD/role/ID binding、
UNKNOWN/ATTEMPTING ledgerと否定watermark、同record owner更新とmain唯一writer再照合を候補実装。
policy opt-inの#100だけへMerge/Completion条件を接続。既存再開CLIのpurpose、claim前receipt拒否、
同期adapterと否定履歴を維持し、公開collectorの準備Gate再収集を無効にして自己参照を防止。
既存read-only adapterは公開GETをtoken任意とし、正式pluginの実ZIPを既存readerへ渡す任意指定を追加。writer/POST/PATCHのtoken必須は維持。実CLI経路のmain反映後実証は未完了。
旧I-09/旧優先順位は今回の明示指示に従いI-07統合/I-01優先へ置換。

区分: コード・契約・検証・運用手順の追加実装。main適用、Work実登録、実イベント、実受領、
実ZIP/実次操作、同共有recordのlive smoke、停止読戻しはこのLog記述では実施したことにしない。
影響: 添付V3.9の9/10/13/19/20/21節に対応する今回限定の接続。
根拠: Issue100本文とユーザーの専用Cloud task指示。旧Issue96/PR99は背景・未実証管理を維持。

実装済みと実動確認済みを[接続図](i01-preparation-connection.md)で分ける。
本候補の正式Gateはmain反映後のみ。限定初回受入は具体的PR/CI/別Workレビュー/登録準備を
揃えた本担当による新しい人間判断の境界で、過去の導入例外を流用しない。

- policy top-level v2版障壁を追加。新readerのlegacy1互換、旧main実readerの2拒否、既存Issue entry不変を回帰。
- v2 CLIは唯一共有inputのREST投稿者認証・現在main policy binding・local案一致を必須とし、認証後API失敗の否定保存と古い肯定二度の再投入をCLI subprocessで回帰。
