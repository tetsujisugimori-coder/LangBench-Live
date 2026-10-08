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

- 独立Work実指摘comment6053210723のF1/F2/F3をIN_SCOPE blockingとして補修。進捗NO_OPと拒否時刻保存を分離、同digest未解決ledgerの消失を禁止、承認済みrole eventsをinputへ束縛。実opened deliveryは本担当回収済みだがrun ID UNKNOWN、修正HEADの独立再照合/正式PASSは未受領。

- 共有comment容量をv2限定で60000文字相当/240000UTF8bytesの二重上限へ補修。CLI/collector/writer共通の完成本文renderで検証し、詳細Prompt/多phase履歴/合成handoffを保持、容量不足で正式PASS不可。GitHub一次資料とREST上限保証の限界を運用文書へ記載。
- 本担当実要約6052718244に基づきPR101の両登録/両保存UI読戻し完了・review実opened受信を図へ反映。owner未来受信/実再開/I01成功は未確認、最終修正HEADの独立PASSは未受領。

- 二重上限だけでは全phaseの詳細Prompt履歴が文字上限を超えるため、writer専用snapshot.stateにstrict可逆zlib-base64-v1表現を追加。全文input/owner/historyは維持、bounded展開/digest/canonical inert JSON/単一stream/旧raw-v2互換を検証する。同じ共有comment以外の保存場所は作らない。
