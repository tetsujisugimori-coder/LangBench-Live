# LangBench Live

## Windows CPU topology の観測

`python tools/cpu_topology.py [--output PATH]` はWindowsのprocessor group、logical processor、物理coreと現在のプロセスaffinityを読み取り、端末に要約を表示します。`--output` を指定すると詳細JSONも保存します。通常のPythonベンチマーク結果では `environment.cpu_topology` に同じ診断情報をoptional fieldとして記録します。失敗は診断status/errorとして残り、ベンチマークを止めません。非Windowsでは `unsupported` になります。

使用APIは `GetActiveProcessorGroupCount` / `GetActiveProcessorCount`、`GetLogicalProcessorInformationEx(RelationProcessorCore)`、`GetProcessAffinityMask` / `GetThreadGroupAffinity` です。取得情報は観測だけに使い、affinityやthread設定を変更しません。coreごとのWindows efficiency classは生値として記録しますが、P-core / E-coreとは分類しません。Processor groupをまたぐprocess affinityの厳密な集合表現は未対応で、affinityには現在のthread groupに対するAPI scopeを明記します。

## Windows C/direct CPU affinity 診断

通常のベンチマーク設定は変更せず、専用スクリプトで normal、指定した論理CPU A、論理CPU Bを比較します。normal→A→B の固定順では時間経過と条件が交絡するため、3条件を N→A→B、A→B→N、B→N→A の順に決定的にローテーションします。診断系列ごとにCを一度だけ `gcc -O2 -std=c11 -Wall -Wextra` でコンパイルし、同じ実行バイナリ、入力1〜1,000,000、direct→function_call、各ケースのウォームアップ5回・測定50回で実行します。affinityはCプロセス自身がセットアップ前にWindows APIで設定・確認します。normalには設定引数を渡しません。CPU番号は現在のWindowsプロセッサグループ内の論理CPU番号で、プロセスに許可されたmaskから選んでください。

```powershell
python -B tools/diagnose_c_affinity.py --runs 40 --cpu-a 0 --cpu-b 1 --output results/diagnostics/c-affinity-<一意な名前>
```

`--runs` は各条件の回数で、40なら40サイクル計120run、3サイクル9runの動作確認なら `--runs 3` を指定できます。指定CPUがプロセスの許可mask外、2番号が同一、Windows以外の場合は測定前にエラーにします。保存先が既存の場合も上書きしません。測定前に全runのexperiment ID・run番号・順序・サイクル・位置・一意な番号付きrun ID・pending状態を `plan.json` と `runs.json` に保存します。`plan.json`は実行中に変更しません。`runs.json`は完了ごとに原子的に更新し、各回の条件・CPU番号（normalはnull）・開始終了時刻・50件のdirect生サンプル・中央値・最小最大・0.2 ms以上の件数・ベンチマーク条件・バイナリSHA-256・成否を残します。番号付きrun IDは診断時だけ受理し、通常の正式結果Validatorと3言語履歴の受理規則は維持します。元の結果JSONとログも各回ごとに保存します。`summary.json`には条件別と実行位置×条件別の計画・成功・失敗run数、run中央値の中央値・平均・母標準偏差・範囲、全サンプル数、0.2 ms以上のサンプル数と該当run数を保存します。cycleごとの推移は`runs.json`のcycle・position・condition・medianから再構築できます。個別runの失敗は記録して残りを続行し、バイナリSHA・測定設定・affinity確認が不一致なら系列を停止します。静的なOS・CPU情報は記録しますが、CPU周波数・電源状態は測定しません。

raw診断データはGit管理外の`results/diagnostics/<系列名>/`に保存します。第三者が読める再現用データは`artifacts/c-affinity/public-data.json`と`summary.md`に保存し、raw `plan.json`・`runs.json`・最適化解析ファイルおよび各runの元結果JSONのSHA-256を対応付けます。公開JSONには再集計に必要な50 samples、実験条件、OS/CPU、run ID、binary/source SHAとcondition・position別統計を含め、実行パスやバイナリは含めません。公開データは診断rawから次のように生成し、公開JSON単体からsummaryを再計算して整合性を確認できます。

```powershell
python -B tools/publish_c_affinity.py results/diagnostics/<系列名> --public-output artifacts/c-affinity/public-data.json --table-output artifacts/c-affinity/summary.md
python -B tools/publish_c_affinity.py --recalculate-public artifacts/c-affinity/public-data.json --table-output artifacts/c-affinity/summary.md
```

normalのみ変動して固定CPUで安定すればスケジューリングやCPU移動を、特定CPUだけ遅ければCPU間の差を、全条件で変動すればaffinity以外の要因を追加調査する材料になります。全条件で安定なら稀な外乱を含め長期観測を検討します。いずれも原因の確定判定ではありません。50サンプルは各run内の反復であり、独立した50実験ではありません。

## C測定順の追加診断：事前固定40回（2026-09-24）

マージ済みPR #24を起点とし、通常の3言語履歴・通常結果JSON・C測定本体は変更せず、専用の[`tools/diagnose_c_measurement_order_followup.ps1`](tools/diagnose_c_measurement_order_followup.ps1)で別系列を実行します。実行前に40回の`plan.json`と全40回の未確定行を含む`runs.json`を保存します。20組の各ペアにA（direct→function_call）とB（function_call→direct）を1回ずつ置き、AB/BAは各10組です。各組の一方だけを監視し、A/B×監視あり/なしは各10回、各条件のペア内先・後は各5回です。結果を見て計画を変更しません。

入力1〜1,000,000、ケースごとのウォームアップ5回・50サンプル、checksum 500000500000、`gcc -O2 -std=c11 -Wall -Wextra`、CのQPC trace、別プロセスの`GetSystemTimes`監視間隔20 msはPR #24と同じです。ランナーはC結果の検証、trace検証、監視の起動・終了・ファイル取得・内容検証を別々に記録し、監視プロセスを待ってからその回の状態を確定します。監視に失敗してもC成功を失敗に読み替えません。失敗理由、ログ、取得済みの元JSONはローカルの専用ディレクトリに残します。

```powershell
pwsh -NoProfile -File tools/diagnose_c_measurement_order_followup.ps1 -PlanOnly
pwsh -NoProfile -File tools/diagnose_c_measurement_order_followup.ps1 -OutputDirectory results/diagnostics/<一意な系列名>
python -B tools/c_order_followup.py results/diagnostics/<一意な系列名> --public-output <新しい公開JSONの保存先> --table-output <新しい表の保存先>
```

最初の`c-order-followup-20260924-fixed40-01`はC実行で元JSONとtraceを40回取得し、監視予定20回のプロセス・ファイル・内容検証も成功しました。しかしランナーが生成した実験IDが既存Validatorの形式に合わず、C結果の検証は40/40回失敗しました。この系列を成功系列へ混ぜず、[失敗系列の公開JSON](artifacts/c-order-followup/attempt-01-public-data.json)と[表](artifacts/c-order-followup/attempt-01-summary.md)に全40回の状態と元ファイルのSHA-256を残しました。取得した元ファイルは無視対象のローカルディレクトリに保持しています。

ID形式を直し、コードコミット`1a740c8`から別の`c-order-followup-20260924-fixed40-02`を2026-09-24 13:52:03〜13:54:39 JSTに実行しました。C結果とtraceは各40/40回成功、監視は予定20/20回で起動・終了・ファイル取得・内容検証に成功しました。監視観測のCPU値は2210/2308件で有効、98件は欠測です。[公開JSON](artifacts/c-order-followup/public-data.json)には全サンプル、QPC時刻、監視区間と元`plan.json`・`runs.json`・各回の結果・trace・監視ファイルのSHA-256を記録し、ローカルパスや個人情報を除外しました。[集計表](artifacts/c-order-followup/summary.md)は公開JSONのサンプルから条件別の中央値と0.2 ms以上の回数・サンプル数、連続位置、各回の欠測、遅いサンプルと監視区間のQPC重なりを示します。旧形式1.0/2.0の集計器と公開データは引き続き読めます。

| 順序 | 監視 | 予定/C成功/監視成功 | direct中央値の範囲（ms） | 0.2 ms以上の回数/サンプル数 |
|---|---|---:|---:|---:|
| A | あり | 10/10/10 | 0.1025〜0.1525 | 0/0 |
| A | なし | 10/10/対象外 | 0.096〜0.104 | 2/2 |
| B | あり | 10/10/10 | 0.096〜0.115 | 1/2 |
| B | なし | 10/10/対象外 | 0.096〜0.113 | 0/0 |

監視ありBの23回目ではdirectの1番と42番が各0.208 msで、いずれも監視観測97番のQPC区間`2362885502686–2362885705992`と重なりました。この観測のCPU使用率は約20 ms平均の19.35%です。二つの約0.2 msサンプル時点の負荷や遅延原因は分かりません。Aの監視あり10回には0.2 ms以上がなく、PR #24で見えたAの連続した遅い区間が監視ありにも再現するかは判定不能です。監視なしの回は「CPU観測なし」、監視失敗の回は「取得失敗」と分け、監視ありでもCPU値が欠測した1回目のdirect 50サンプルを欠測として示します。0.2 msは記述用の目安で、有意差の判定基準ではありません。50サンプルは各回内の反復であり、独立した50実験として扱いません。

公開成果物はローカルの元ディレクトリから上記の集計コマンドで再生成できます。既存の公開ファイルを上書きしないため、確認時は新しい出力先を指定してください。Python全86件、C順序2件、C解析16件、C OS版5件、JavaScript22件、manifest検証、公開ファイルの再計算・SHA-256照合を実施しました。20 ms程度のCPU平均では短い負荷変動を見逃し得るため、QPC区間の重なりからCPU負荷が原因だとは判断しません。

## Cの時刻・CPU監視診断（2026-09-24）

PR #21の測定順診断を拡張し、診断時だけCの各ケース・各50サンプルの開始／終了QPCカウンタ値を専用`run-NN-trace.json`へ保存します。通常の結果JSON、3言語履歴、比較判定は変更しません。監視なしの回にも同じC時刻記録を行います。

```powershell
pwsh -NoProfile -File tools/diagnose_c_measurement_order.ps1 -PlanOnly
pwsh -NoProfile -File tools/diagnose_c_measurement_order.ps1 -OutputDirectory results/diagnostics/<一意な名前>
python -B tools/summarize_c_order_diagnostic.py results/diagnostics/<一意な名前> --public-output artifacts/c-order-monitor/public-data.json --table-output artifacts/c-order-monitor/summary.md
```

ランナーは実行前に20回の計画を表示し、`plan.json`と`runs.json`へ保存します。各組はA（direct→function_call）とB（function_call→direct）を1回ずつ含み、AB/BA各5組です。各組の一方だけを監視し、A/Bそれぞれ監視あり5回・なし5回、実行位置では監視あり前半6回・後半4回です。計画は結果に応じて変えません。入力1〜1,000,000、各5回のウォームアップ、各50サンプル、checksum 500000500000、`gcc -O2 -std=c11 -Wall -Wextra`は維持します。

監視ありでは別プロセスが約20 msごとにWindowsの`GetSystemTimes`からシステム全体のCPU使用率を取得し、各観測区間のQPC開始・終了、取得処理の所要時間、取得失敗を`run-NN-monitor.json`に保存します。電源状態とCPUクロックは信頼できる軽量な取得経路を採用していないため記録しません。Cと監視は同じWindows QPCの生カウンタ値と周波数を使い、周波数一致を検証してから区間の重なりを計算します。Cの`FILETIME`とQPCの前後アンカーからUTC表示を概算します。UTC表示同士で重なりを判定しません。アンカーの読取幅は公開データに記録しますが、時計自体の誤差を保証するものではありません。

ローカル元ファイルは`results/diagnostics/<名前>/`に残します。公開用の[JSON](artifacts/c-order-monitor/public-data.json)には結果・時刻・監視元ファイルのSHA-256とファイル名、全サンプルと監視観測値を入れ、cwd、コンパイルコマンド、ローカルパスを除外します。[集計表](artifacts/c-order-monitor/summary.md)は公開JSONの元サンプルから中央値と0.2 ms以上の件数を再計算し、CPU観測の欠測も表示します。既存の[PR #21公開JSON](artifacts/c-order-diagnostic/public-data.json)と表も従来どおり読めます。

Windows実機で12:48:25〜12:49:21 JSTに最終ソースSHA-256 `c2698ab13afb0275055cf9412797bfe0c99f49d9fe3d10a0d3589941db3a1eda`の20回を逐次実行し、20/20成功しました。監視あり10回でCPU値は1143/1202観測（95.1%）有効でした。実際の採取間隔の回別中央値は20.62〜20.77 ms、最大25.81 ms、取得処理時間の回別中央値は0.148〜0.297 ms、最大4.598 msです。これは取得処理自体の時間であり、監視プロセス全体の干渉量ではありません。C/directの0.2 ms以上はA・監視なしの2回に計18/250件、他のA・監視あり、B・監視あり／なしでは0件でした。遅い18件の測定中CPU観測はありません。監視ありの各C/directケースには有効観測が1〜2区間重なりましたが、20 ms程度のCPU平均値から0.1〜0.3 msの個別サンプル時点の負荷は特定できません。

50サンプルは各実行内の反復で、独立した50実験ではありません。20 msより短い負荷変動は見逃し得ます。CPU値の欠測は低負荷を意味しません。監視あり／なしの差や時刻上の重なりだけから、遅延の原因や統計的有意差は判断できません。別の事前固定系列による確認は上記の40回追加診断に記録しました。

## Cの測定順診断（2026-09-24）

通常の `benchmarks/function_call_numeric_sum/run_all.ps1` は従来どおり **A: direct → function_call** で実行し、3言語の共通履歴に保存します。C単独の診断では **B: function_call → direct** を明示的に選べます。両順序で同じC関数、1〜1,000,000の入力、ウォームアップ各5回、各50サンプル、checksum 500000500000、`gcc -O2 -std=c11 -Wall -Wextra` を使います。

```powershell
pwsh -NoProfile -File tools/diagnose_c_measurement_order.ps1 -PlanOnly
pwsh -NoProfile -File tools/diagnose_c_measurement_order.ps1 -OutputDirectory results/diagnostics/c-order-<任意の一意な名前>
```

診断スクリプトは各組にAとBを1回ずつ入れ、ABを5組、BAを5組、合計20回を事前に固定して逐次実行します。通常ランナーと同じロックを保持し、C結果は回ごとの専用ファイルへ保存します。失敗回は `runs.json` に理由とともに残し、成功数に含めません。端末状態は開始前後に取得できた項目だけを記録します。測定中の負荷は観測していません。逆順結果は通常Validatorが拒否するため、既存の3言語履歴・比較器へ入りません。

`results/diagnostics/<名前>/runs.json` と `run-01.json`〜`run-20.json` はローカルの保存元です。公開用の [`artifacts/c-order-diagnostic/public-data.json`](artifacts/c-order-diagnostic/public-data.json) は元JSONを編集せずに生成した別ファイルで、各回の実順序、全50サンプル、開始・終了時刻、checksum、コンパイラ・オプションと保存元のファイル名・SHA-256を含みます。個人のローカルパスや `compile_command` は含めません。対応する[全20回の表](artifacts/c-order-diagnostic/summary.md)は公開用JSONのサンプルから再計算できます。公開用データを再生成する場合は次を実行します。

```powershell
python -B tools/summarize_c_order_diagnostic.py results/diagnostics/c-order-20260924-final --public-output artifacts/c-order-diagnostic/public-data.json --table-output artifacts/c-order-diagnostic/summary.md
```

最終診断はWindows実機で2026-09-24 12:04〜12:05 JSTに20回すべて成功しました。C/directの回ごとの中央値はAが **0.104〜0.2445 ms**、Bが **0.0965〜0.113 ms**。Aの16回目は中央値0.2445 ms、前半25件0.298 ms・後半25件0.204 msで、38/50件が0.2 ms以上でした。Bの10回には0.2 ms以上のdirectサンプルがありませんでした。0.2 msは記述用の区切りで、判定基準ではありません。実装確認を強める前の20回も隠さず[別の公開用JSON](artifacts/c-order-diagnostic/pilot-public-data.json)と[表](artifacts/c-order-diagnostic/pilot-summary.md)に残しました。この先行系列ではAの0.2 ms以上は計1/500件、Bは計7/500件で、最終系列とは分布が異なります。

50サンプルは1回の実行内の反復で、50回の独立実験ではありません。この20回だけで測定順が遅い区間の原因だと確定したり、統計的有意差を主張したりしません。旧履歴とはCソースが異なり、測定中の端末負荷も観測していないため、旧履歴との数値差にもこの制約があります。Cの解析資料は変更後ソースから再生成し、manifestのソースハッシュと照合しています。

## 概要

複数のプログラミング言語で同じベンチマーク処理を実行し、コード・ログ・実測結果を比較する学習用アプリです。

## v0.1 の目的

PythonでCSVファイル readingTest.csv を読み込み、データ行数と処理時間を計測し、結果をJSONに保存します。

## フォルダ構成

```text
LANGBENCH-LIVE/
  data/
    readingTest.csv
  benchmarks/
    line_count/
      python/
        main.py
      javascript/
        main.js
      c/
        main.c
  results/
    python_result.json
    javascript_result.json
    c_result.json
  tools/
    create_sample_csv.py
  README.md
  LOG.md
```

## 実行方法

```bash
python benchmarks/line_count/python/main.py
```

JavaScript版はNode.jsで実行します。

```bash
node benchmarks/line_count/javascript/main.js
```

C版はPowerShellでコンパイルしてから実行します。

```bash
gcc benchmarks/line_count/c/main.c -o benchmarks/line_count/c/main.exe
.\benchmarks\line_count\c\main.exe
```

## CSV生成スクリプト

`tools/create_sample_csv.py` は、ベンチマーク用のサイズ違いのCSVをまとめて生成する補助スクリプトです。

CSV sample files are not committed to the repository.
Generate them locally with:

```bash
python tools/create_sample_csv.py
```

作成されるファイルは次の3つです。

* `data/readingTest_small.csv`: 1,000行
* `data/readingTest_medium.csv`: 100,000行
* `data/readingTest_large.csv`: 1,000,000行

生成されるCSVのヘッダーは `id,name,category,value,memo` です。`category` は `A`, `B`, `C` を順番に繰り返します。

## 出力されるJSON

### function_call_numeric_sum

`function_call_numeric_sum` は、1から1,000,000までの同じ整数配列を、ループ内で直接加算する `direct` と、ループごとに外部定義の加算関数を呼ぶ `function_call` で比較します。配列生成・確保、JSON生成、環境取得、出力は測定区間に含めません。各ケースは5回ウォームアップし50回測定します。

```powershell
powershell -ExecutionPolicy Bypass -File benchmarks/function_call_numeric_sum/run_all.ps1
```

C版は `gcc -O2 -std=c11 -Wall -Wextra` でコンパイルします。加算関数はMSVCの`__declspec(noinline)`、GCC/Clangの`__attribute__((noinline))`でインライン化を抑制しますが、非対応コンパイラでの呼び出し保持は保証できません。JavaScriptではV8のJITがインライン化する場合があります。この実験は関数呼び出しを含む特定ループの比較であり、言語全体の性能を示すものではありません。

Cの `environment.os_version` は、`ntdll.dll` の `RtlGetVersion` が返す実行中のWindows NT版の major.minor.build を文字列にした値です。表示名や更新リビジョン（UBR）は含みません。`GetVersionEx` は実行ファイルの manifest によって返値が変わるため使用しません（[Microsoftの説明](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getversionexa)、[RtlGetVersion](https://learn.microsoft.com/en-us/windows/win32/devnotes/rtlgetversion)）。APIの取得・呼び出しに失敗した場合、Cは `status=error` と理由を標準エラーに出して終了し、その回の新しい結果JSONを保存しません。`run_all.ps1` 経由でもC単独の `c/run_c.ps1` 経由でも同じC実行ファイルがこの処理を行います。

各言語は従来どおり `results/function_call_numeric_sum_<language>_result.json` に最新結果を出力します。`run_all.ps1` は3結果を検証した後、`results/history/<experiment_id>/<archive_id>/` へ一組として追記保存します。同じ秒に実行して `experiment_id` が重なっても、保存フォルダは毎回異なります。`archive.json` には各JSONのSHA-256と元の `run_id` を記録します。履歴フォルダはGit管理の対象外なので、必要に応じて別途バックアップしてください。

この実験の現在の条件は `experiments/function_call_numeric_sum.json` に記録します。履歴保存時に3言語の出力の `config` と `validation.expected_checksum` をこの定義と照合し、定義と一致しなければ保存しません。保存に成功すると、そのとき使用した定義のバイト列を履歴内の `experiment.json` にコピーし、`archive.json` にそのSHA-256を記録します。後からリポジトリ側の定義を変更しても、過去の条件を確認できます。定義を変更するだけで測定条件が切り替わる仕組みではなく、各言語の測定コードに設定した値との一致を検査する段階です。

`archive_id` は保存した3言語一組を区別する一意のIDです。保存済みの各言語結果を指す際は `archive_id` と言語名を組にしてください。既存の秒単位の `run_id` は引き続き結果に残りますが、一意の保存キーには使いません。

表示された `archive_path` の結果は現行Validatorで再検証できます。

```powershell
$archive = "results/history/<experiment_id>/<archive_id>" # 表示されたarchive_pathに置き換える
python tools/validate_result_json.py "$archive/python.json" "$archive/javascript.json" "$archive/c.json"
```

### 保存済み履歴2件の比較条件判定

測定値を比較する前に、保存された履歴フォルダ2件を指定して判定できます。読み取り専用で、履歴や最新結果を更新しません。

```powershell
python tools/compare_archives.py "results/history/<experiment_id>/<archive_id>" "results/history/<experiment_id>/<archive_id>"
python tools/compare_archives.py --json "results/history/<experiment_id>/<archive_id>" "results/history/<experiment_id>/<archive_id>"
```

各履歴の `archive.json`、`experiment.json`、C・JavaScript・Pythonの結果を読みます。記録された4件のSHA-256を実ファイルの**生バイト列**から再計算し、ファイル参照、重複、JSON構造、既存Validator、履歴内の定義と各結果の実験ID・benchmark・config・期待checksumの一致を検査します。判定にはその履歴の `experiment.json` を使用し、現在のリポジトリの定義を過去の履歴へ当てはめません。欠落、改変、検証失敗は判定ではなくエラーです。

判定は次の3種類です。

* **比較可能** (`comparable`): 保存された実験条件と、点検対象の環境・処理系・ソース情報が一致します。
* **注意付き** (`caution`): 実験条件は一致しますが、同じ言語同士のOS・OS版・CPU名・アーキテクチャ、処理系・版、Cコンパイラ・版、記録された起動／コンパイルオプション、利用可能なソースSHA-256に差または情報不足があります。
* **比較不可** (`incomparable`): 保存された定義のbenchmark、schema_version、config、expected_checksumのいずれかが異なります。

異なる言語同士の処理系の違いは注意理由にしません。Cの `compile_command` には毎回異なる一時ファイルパスが含まれるため、コンパイルオプションには結果の `optimization_analysis.provenance.current.options` を使います。これが無ければ情報不足とします。`run_id`、`experiment_id`、`archive_id`、保存日時は実験条件に含めません。`experiment.json` のSHA-256は改変検出だけに使い、JSONの空白やキー順の違いは条件差としません。

`--json` は `schema_version: "1.0"`、入力を表す `left` / `right`、英語の `verdict`、`reasons` 配列を出力します。各理由は安定した `code`、対象の `field`、日本語の `message`、言語固有なら `language` を持ちます。例: `{"verdict":"caution","reasons":[{"code":"INFORMATION_MISSING","field":"environment.os_version","message":"c の environment.os_version が片方または両方で記録されていません。","language":"c"}]}`。実際の出力には `schema_version` と2つの入力パスも含まれます。正常な判定は3種類とも終了コード0です。履歴が壊れている場合は終了コード2で、JSONモードでは `{"error":{"code":"...","message":"..."}}` を返し、`verdict` は返しません。

これは記録済み項目の一致判定です。CPU名が同じでも同一マシンとは証明できず、負荷や電源状態など未記録の要因も確認しません。ソースSHA-256は結果に記録された値同士の比較で、ソースファイル原本は履歴に保存されていません。速度順位、統計的有意差、最適化の因果関係は判定しません。外部ツールは `verdict` と理由コードを扱い、測定値の解釈にはこれらの制約を併記してください。

### 保存済み履歴2件の測定値表示

`tools/show_archive_metrics.py` は、左・右の履歴を読み取り専用で検証し、同じ言語（C、JavaScript、Python）の同じケース（`direct`、`function_call`）の中央値を並べます。`compare_archives.py` の履歴読み込み・SHA-256照合・既存Validator・比較条件判定をそのまま使用します。履歴フォルダと最新結果は更新しません。

```powershell
$left = "results/history/<左のexperiment_id>/<左のarchive_id>"
$right = "results/history/<右のexperiment_id>/<右のarchive_id>"
python tools/show_archive_metrics.py $left $right
python tools/show_archive_metrics.py --json $left $right
```

差は **右の中央値 − 左の中央値**（ms）、変化率は **(右の中央値 − 左の中央値) ÷ 左の中央値 × 100**（%）です。時間が短い方が速いので、通常の正の中央値では正の差・変化率は右が遅いこと、負なら右が速いことを表します。各履歴の検証済み `samples_ms` から既存Validatorと同じ規則（昇順に並べ、偶数件なら中央2値の平均）で中央値を再計算し、その値を表示・差・変化率・速度の方向に共通して使います。保存済み `median_ms` はValidatorで照合しますが、このCLIの計算には使いません。テキストの丸めは表示時だけに行い、`--json` は計算結果を表示用に丸めません。履歴JSONは書き換えません。

* `comparable`: 6ケースの両履歴の中央値、差、変化率、中央値に基づく速度の方向を表示します。
* `caution`: 同じ数値を**参考値**として表示し、判定理由の `code`、`field`、説明を必ず併記します。実測履歴ではCの `environment.os_version` が未記録のため、`INFORMATION_MISSING` が出ることがあります。
* `incomparable`: 条件が異なる理由と各履歴の単独の中央値だけを表示します。差・変化率・速度の優劣はテキストに出さず、JSONにもそれらのキーを入れません。
* 履歴の改変・欠落・Validator失敗: 数値は出さず終了コード2の検証エラーにします。`--json` では既存コマンドと同様に `{"error":{"code":"...","message":"..."}}` のみを返し、`verdict` や `measurements` を返しません。正常な3判定の終了コードは0です。

JSONレポートの `schema_version` は `"1.0"` です。`left` / `right` はそれぞれ指定した `path`、保存単位の `archive_id`、実験単位の `experiment_id`、保存時刻 `archived_at` を持ちます。`verdict` と `reasons` は既存の `compare_archives.py` と同じ値・理由構造です。`measurements` は6件の配列で、`language` と `case` が組を識別します。`left_median_ms` / `right_median_ms` は各履歴の検証済み `samples_ms` から再計算した中央値（ms）です。比較可能・注意付きの場合だけ、`delta_ms`（右−左、ms）、`change_percent`（左基準、%）、`faster`（`left` / `right` / `equal`、再計算した中央値だけに基づく方向）を含みます。`equal` は両中央値が一致する意味で、サンプル分布全体の一致を意味しません。左中央値が0なら `change_percent: null` と `change_percent_unavailable_reason: "LEFT_MEDIAN_ZERO"` を返します。負の左中央値も時間の比率として解釈せず `LEFT_MEDIAN_NEGATIVE`、有限な計算結果にならない場合は対象の値を `null` とし `NONFINITE_RESULT` を付けます。`Infinity` や `NaN` は出力しません。

例: サンプル由来の中央値が左1.5 ms、右3 msなら `delta_ms: 1.5`、`change_percent: 100.0`、`faster: "left"` です。両方のサンプルが `[1.0, 2.0]` で、右の保存 `median_ms` だけが1.5005 msでも、表示は両方1.5 ms、差0 ms、変化率0%、`faster: "equal"` です。注意付きの場合もこれらの値には必ず `verdict: "caution"` と理由が付きます。`incomparable` の各要素には `language`、`case`、両中央値のみが入ります。既存の `compare_archives.py --json` の形式は変更していません。

保存結果の `median_ms` は既存Validatorが `samples_ms` から中央値を再計算し、`math.isclose` の相対許容誤差 `1e-9` と絶対許容誤差 `0.001` ms で照合した値です。保存値とサンプル由来の中央値の厳密な一致は保証されません。このCLIは検証済みサンプルから求めた中央値の記述的な差を示すだけです。50サンプルは1回の実行内の反復であり、50回の独立した実験、統計的有意差、最適化の因果関係、異なる言語間の総合順位を示しません。未記録の負荷・電源状態なども判定できません。

### 独立した複数回の履歴で中央値の揺れを確認する

Windowsで同じチェックアウト、同じソースと設定のまま `run_all.ps1` を順番に5回実行します。各回の出力にある `archive_path` を1件ずつ控えてください。スクリプトは各回の最新結果も出力しますが、下記の閲覧CLIは履歴と最新結果を変更しません。

```powershell
1..5 | ForEach-Object {
    pwsh -NoProfile -File benchmarks/function_call_numeric_sum/run_all.ps1
    # 各回に表示された archive_path を控える
}
$archives = @(
    "results/history/<1回目のexperiment_id>/<1回目のarchive_id>",
    "results/history/<2回目のexperiment_id>/<2回目のarchive_id>",
    "results/history/<3回目のexperiment_id>/<3回目のarchive_id>",
    "results/history/<4回目のexperiment_id>/<4回目のarchive_id>",
    "results/history/<5回目のexperiment_id>/<5回目のarchive_id>"
)
python tools/show_archive_variability.py @archives
python tools/show_archive_variability.py --json @archives
```

`tools/show_archive_variability.py` は異なる履歴フォルダを2件以上受け付けます。各履歴の `archive_id`、`experiment_id`、`archived_at` とC・JavaScript・Pythonの `direct` / `function_call` の計6中央値を表示し、全組を既存の2履歴判定で調べます。5履歴なら10組です。全組が `comparable` のときだけ実行間の最小中央値・最大中央値・差（最大−最小、ms）を通常の比較値として示します。`caution` を含み `incomparable` がなければ、それらを**参考値**として示し、各組の原因コードと対象フィールドを添えます。CのOS版 `environment.os_version` が未記録なら、同じマシンの5回でも `INFORMATION_MISSING` の `caution` になり得ます。`incomparable` を含む場合は6ケースそれぞれの各履歴の中央値だけを示し、集団の最小・最大・差は出しません。不正・改変履歴、同一フォルダの重複指定は検証エラーです。別の場所にコピーされた履歴でも、検証後の `archive_id` が重複すれば同じ測定として `DUPLICATE_ARCHIVE` エラーにし、集計値は出しません。

以前のCのOS版が `null` の履歴はそのまま保持します。新しい版記録済み履歴同士は他の条件も一致すれば `comparable` になりますが、新旧の組は引き続き `INFORMATION_MISSING` / `environment.os_version` の `caution` です。保存履歴のJSONやSHA-256を書き換えて注意判定を消さないでください。

JSONは `unit: "ms"`、全体の `verdict`、`runs`（入力順の身元情報と6中央値）、`pairwise.counts`、`pairwise.pairs`（0始まりの入力位置、判定、理由）を分けます。集団の数値を出せるときだけ `aggregate` を含み、その `status` は `comparable` または `reference`、`cases` に6ケースの `min_median_ms`、`max_median_ms`、`range_ms` を入れます。差が有限値にならない場合は `range_ms: null` と理由コードを返し、NaNやInfinityは出しません。中央値は各回の50個の `samples_ms` から既存Validatorと同じ関数で計算します。5回の範囲は記述的な揺れであり、統計的有意差、最適化の効果、言語全体の優劣を判定しません。

`run_all.ps1` 同士の同時実行はロックで防ぎます。各言語のスクリプトを単独で同時起動した場合は、従来の固定名ファイルを共有するため履歴保存の対象外です。`results.direct` と `results.function_call` はそれぞれのサンプルと統計値を持ち、`validation` は両ケースと期待値の合計（checksum）が一致したことを示します。

`jit_object_numeric_sum` の結果は、既存のファイル命名規則に従って次へ保存されます。

* Python: `results/jit_object_numeric_sum_python_result.json`
* JavaScript: `results/jit_object_numeric_sum_javascript_result.json`
* C: `results/jit_object_numeric_sum_c_result.json`

3言語を同じ実験条件で比較する場合は、共通ランナーを使用します。ランナーが1つの `experiment_id` を生成して各言語へ渡します。

```powershell
powershell -ExecutionPolicy Bypass -File benchmarks/jit_object_numeric_sum/run_all.ps1
```

単独実行時は各プログラムが `experiment_id` と `run_id` を生成します。外部から指定する場合は `--experiment-id=<ID>` および `--run-id=<ID>`（C版ランナーでは `-ExperimentId` および `-RunId`）を使用します。

`run_id` は各起動を識別するための補助IDで、形式は `YYYYMMDD_HHMMSS_<language>_<benchmark>` です。秒単位で生成するため、同じ言語・同じベンチマークを同一秒内に複数回起動すると重複し得ます。データベース上の一意キーとして単独では使用せず、永続保存時は `experiment_id`、`run_id`、`language`、`created_at`、取込側IDなどを組み合わせて識別してください。

### 結果JSON正式仕様（schema 1.0）

新しく生成する結果JSONのルート構造とキー順は次の形式に統一しています。

```json
{
  "type": "langbench_result",
  "schema_version": "1.0",
  "project": "LangBench Live",
  "benchmark": "jit_object_numeric_sum",
  "experiment_id": "20260712_073000_jit_object_numeric_sum",
  "run_id": "20260712_073018_python_jit_object_numeric_sum",
  "language": "python",
  "created_at": "2026-07-12T07:30:18+09:00",
  "status": "success",
  "engine": {
    "runtime": "python",
    "runtime_version": "3.x.x",
    "compiler": null,
    "compiler_version": null,
    "python_implementation": "CPython"
  },
  "execution": {
    "runner": "vscode_terminal_powershell",
    "runner_label": "VSCode Terminal / PowerShell",
    "cwd": "C:/Users/...",
    "argv": ["python", "benchmarks/jit_object_numeric_sum/python/main.py"]
  },
  "environment": {
    "os": "Windows",
    "os_version": "10.0.x",
    "architecture": "AMD64",
    "cpu": null,
    "logical_processors": 20,
    "memory_bytes": null
  },
  "build": null,
  "config": {
    "item_count": 1000000,
    "warmup_iterations": 5,
    "measurement_iterations": 3,
    "numeric_type": "integer",
    "value_field": "value"
  },
  "timing": {
    "process_startup_ms": null,
    "setup_ms": 120.125,
    "warmup_ms": 48.5,
    "measurement_ms": 28.49,
    "benchmark_total_ms": 197.115
  },
  "results": {
    "samples_ms": [9.5, 9.48, 9.51],
    "min_ms": 9.48,
    "max_ms": 9.51,
    "mean_ms": 9.497,
    "median_ms": 9.5
  },
  "validation": {
    "checksum": 500000500000,
    "expected_checksum": 500000500000,
    "tolerance": 0,
    "passed": true
  },
  "error": null
}
```

`benchmark` は処理名であり、同じ処理を行う3言語で同じ値です。旧 `experiment` キーは廃止しました。`experiment_id` は同じ条件で比較するC・Python・JavaScriptの共通グループID、`run_id` は言語ごとの1回のプログラム起動を表すIDです。プログラム内部の50回の本測定は50 runではなく、1 run内の `results.samples_ms` へ格納されます。

`build` は任意のビルド工程情報です。PythonとJavaScriptでは `null`、コンパイルが必要なCでは `required`, `compiler`, `compiler_version`, `compile_command`, `compile_ms`, `source_path` を持つオブジェクトです。`engine` は実行時のランタイム情報、`build` はコンパイル工程として役割を分離しています。`compile_ms` はベンチマーク時間には含めません。

`timing.setup_ms` はデータ生成、`warmup_ms` はウォームアップ全体、`measurement_ms` は本測定全体を表します。`benchmark_total_ms` はこの3値の合計で、プロセス起動、環境情報取得、JSON生成、ログ出力、ファイル保存は含みません。正確に測れない `process_startup_ms` は `null` です。

`validation.checksum` は全反復の合計ではなく1回分の計算結果です。各反復が同じ値になることを実行中に確認し、期待値との一致を `passed` に保存します。取得不能値は空文字や `unknown` ではなく `null` とします。成功時の `error` も `null` です。

`status: "error"` の結果では、未取得のtimingと統計値を `null`、`samples_ms` を空配列、`validation.passed` を `false` とし、`error.type` と `error.message` に空でない文字列を保存します。エラー結果には測定反復数とサンプル数の一致を要求しません。

言語間の比較結果、ランキング、Python比などの派生値は個別の結果JSONへ含めません。Memo Nexusなどの読込側で複数JSONから算出します。`tools/validate_result_json.py` は正式形式を検証し、補助関数 `normalize_legacy_result` では旧 `samples`、`min`、`max`、`mean`、`median`、`iterations`、`array_size`、`object_count`、`total_ms`、ルート直下の `checksum`、`experiment` を読み替えられます。

### 最適化解析プロトタイプ

`optimization_analysis` は、測定値である `results` とは分離して、性能に影響した可能性のある最適化を調査した結果を保存するプロトタイプです。schema 1.0では任意フィールドで、存在する場合は `build` と `config` の間に置きます。従来の結果JSONはこのフィールドがなくても引き続き有効です。現在は `function_call_numeric_sum` のC・Python・JavaScript版だけが出力します。

保存済み解析の条件と、その解析資料から実際に抽出した結論は `artifacts/function-call-analysis/manifest.json` の `condition` と `findings` に記録します。結果JSONでは同じ結論を `provenance.artifact_findings` に保持します。`provenance.analysis` と `provenance.current` のソースSHA-256、処理系名・バージョン、CPUアーキテクチャ、主要オプションがすべて一致した場合だけ `status: "matched"` となり、現在値へ `artifact_findings` を採用します。不一致項目は `mismatches` に入り、対象判定は `not_checked` へ降格します。

manifestが存在しない、JSONや必須構造が壊れている、`findings`や`evidence`が不正な場合は `status: "unavailable"`、対象判定は `unknown` として測定自体を継続します。各ランナーは対象言語entryを使う前に、manifestルートのキー・schema・解析ID・タイムゾーン付き生成日時と、`c`・`python`・`javascript` の3言語entryすべてを検証します。ファイル不在は `manifest_unavailable`、存在する文書の構文・構造不正は `manifest_invalid` として区別し、どちらの場合も保存済みfindingsやevidenceを結果へ流用しません。この受理条件は `tools/validate_result_json.py --manifest` と共通です。

生成処理はGCCレポートと対象関数のアセンブリ、CPythonバイトコード、対象関数名を含むV8トレースから確認できる結論だけを記録し、確認できない最適化を推測で `detected` や `not_detected` にしません。CのSSE2はx86系アーキテクチャの対象関数で対応命令を確認した場合だけ記録するため、ARM64などへ固定値を流用しません。

```json
{
  "optimization_analysis": {
    "implementation": {
      "name": "CPython",
      "version": "3.14.7"
    },
    "provenance": {
      "status": "matched",
      "artifact_id": "function-call-analysis-20260924-pr9-canonical-python",
      "analyzed_at": "2026-09-23T19:16:37Z",
      "applies_to": ["inlining", "vectorization", "simd"],
      "analysis": {
        "source_sha256": "66c7978695ac300d533a4e419c6949484c076e1fba868c3a43dd96d0392ee217",
        "implementation": {"name": "CPython", "version": "3.14.7"},
        "architecture": "amd64",
        "options": ["optimize=0"]
      },
      "artifact_findings": {
        "inlining": {"result": "not_detected"},
        "vectorization": {"result": "not_detected"},
        "simd": {"result": "not_checked", "isa": []}
      },
      "current": {
        "source_sha256": "66c7978695ac300d533a4e419c6949484c076e1fba868c3a43dd96d0392ee217",
        "implementation": {"name": "CPython", "version": "3.14.7"},
        "architecture": "amd64",
        "options": ["optimize=0"]
      },
      "matched": true,
      "mismatches": []
    },
    "jit": {
      "applicable": true,
      "result": "not_detected"
    },
    "inlining": {
      "result": "not_detected"
    },
    "vectorization": {
      "result": "not_detected"
    },
    "simd": {
      "result": "not_checked",
      "isa": []
    },
    "other_optimizations": [],
    "evidence": [
      {
        "type": "runtime_api",
        "path": "python:sys._jit.is_available/is_enabled"
      },
      {
        "type": "disassembly",
        "path": "artifacts/function-call-analysis/python-bytecode.txt"
      }
    ],
    "notes": []
  }
}
```

固定の解析項目はJIT、インライン化、ベクトル化、SIMDです。`result` の許可値は `detected`、`not_detected`、`not_checked`、`unknown`、`not_applicable` の5種類です。`detected` と `not_detected` は、該当する解析条件が現在条件と一致し、空でない `evidence` がある場合だけ使用します。`not_detected` は最適化が絶対に存在しないという意味ではなく、記録された解析方法では検出されなかったことを表します。

JITでは「処理系に搭載されている」「実行時に有効である」「対象コードで実際に作動した」を区別します。Pythonは `sys._jit.is_available()` と `is_enabled()` を測定外で確認しますが、両方trueでも対象コードのJIT作動を証明できないため、トレースなしでは `unknown` です。JavaScriptはV8トレースと条件が一致した場合だけ `detected` とし、`--jitless`、`--no-opt`等の起動オプションがある実行へ過去の判定を流用しません。

SIMDが `detected` の場合、`isa` は重複のない1件以上の文字列を持ちます。それ以外の結果では `isa` は空配列です。追加項目の `other_optimizations`、根拠の `evidence`、補足の `notes` も配列です。

処理系は言語名とは別に `implementation` へ保存します。JavaScriptの場合、`engine.runtime` はNode.js、`optimization_analysis.implementation` はV8です。CではGCC、Pythonでは実行中の処理系名を記録します。今後、測定された性能差をこの4項目で説明できない場合だけ、必要な項目を `other_optimizations` へ追加していきます。

解析資料とmanifestは次のコマンドで最終ソースから再生成します。`tools/extract_function_call_findings.py` の純粋関数が生成済み資料を読み、manifestの `findings` を構成します。V8の標準出力と標準エラーは別々に収集してから、区切り付きでトレースへ保存します。

`source_sha256` は、解析時と実行時それぞれの実ファイルのバイト列について、CRLFペアだけをLFへ変換した後のSHA-256です。単独のCRや改行以外のバイトは変更しません。`.gitattributes` は新規チェックアウトをLFにしますが、既存のWindows作業ツリーではmainから通常更新しても変更のないソースがCRLFのまま残るため、生成スクリプト、各ランナー、照合テストで同じ定義を使います。生成スクリプトは解析前後のソースハッシュが同じことを確認し、リポジトリを作業ディレクトリにして各処理系を実行します。再生成後はmanifestの構造に加え、3ソースの正規化SHA-256と、保存されたGCC・Python・V8資料から再抽出した `findings` を照合してください。ソース内容、処理系の版、アーキテクチャ、実行オプションが異なる環境の測定では、保存済みの解析結果を条件一致として扱いません。

```powershell
powershell -ExecutionPolicy Bypass -File tools/generate_function_call_analysis.ps1
python tools/validate_result_json.py --manifest artifacts/function-call-analysis/manifest.json
```

## 今後の予定

* C版のベンチマーク追加
* JavaScript版のベンチマーク追加
* 複数言語の結果を同じJSONにまとめる仕組み
* HTMLダッシュボード表示
* 結果表、ランキング、棒グラフ表示
* リアルタイムログ表示
* 過去結果との比較
* 開発現場帳やメモ帳アプリとの連携

# LangBench-Live
色々な言語をベンチマークで比較するアプリ

## C/direct の保存サンプルを調べる（2026-09-24）

`show_archive_samples.py` は既存の `load_archive` によって各履歴の `archive.json` と4ファイルのSHA-256、結果Validator、保存された実験定義との一致を確認してから表示します。履歴は書き換えません。既定はCの `direct` / `function_call`、`--all-languages` でJavaScriptとPythonも表示します。`--json` は入力順の50個の `samples_ms` と、各ケースのサンプル由来の中央値、最小・最大、前半25件・後半25件の中央値を出します。テキストも1〜50の順番を付けて全サンプルを出します。中央値は既存の `median_from_samples` を共用します。欠落・改変・定義不一致は数値を出さず検証エラー（終了コード2）です。

```powershell
python -B tools/show_archive_samples.py "results/history/<experiment_id>/<archive_id>"
python -B tools/show_archive_samples.py --json --all-languages "results/history/<experiment_id>/<archive_id>"
```

同じソース・設定のWindows実機で10回を**逐次**実行する場合は、独立したチェックアウトで次を実行します。`run_all.ps1` の言語順は Python → JavaScript → C、C内は `direct` → `function_call` です。スクリプトはベンチマーク入力ファイルのSHA-256が途中で変わらないことを各回の前後に確認します。各回の開始・終了時刻、成否、失敗理由、`experiment_id`、`archive_id`、履歴パス、順番を `runs.json` に記録し、各履歴を保存後に同じ診断ツールで再検証します。失敗回は成功回に含めません。通常出力は `run-XX.log`、検証済みサンプルは `run-XX-samples.json` に残します。これらは `results/diagnostics/` に置き、Git管理しません。

```powershell
pwsh -NoProfile -File tools/remeasure_function_call.ps1 -Count 10
$record = Get-Content "results/diagnostics/<表示されたフォルダ>/runs.json" -Raw | ConvertFrom-Json
$archives = @($record.runs | Where-Object status -eq 'success' | ForEach-Object archive_path)
python -B tools/show_archive_variability.py --json @archives
python -B tools/show_archive_samples.py --json --all-languages @archives
```

端末状態は各回の**前後だけ**電源プラン、空き物理メモリ、プロセス数を低頻度で取得します。CPU使用率とAC給電状態は信頼できる取得を実装していないため `未取得` と記録します。取得に失敗した項目も `未取得` です。常時監視は行いません。これらの境界時点の値はCの測定中の状態を示しません。

### Windowsで得た観測

PR #17 の5履歴は別のローカル作業ツリーから再読み込みし、50サンプルと定義を検証しました。5履歴の10組は `comparable=10`。以下の `0.2 ms以上` はC/directの分布を見やすくするための記述的な区切りで、判定基準や原因の推定ではありません。Cの各サンプルは0.001 ms単位で保存されるため、その丸め幅程度の差は解釈しません。

| PR #17回 | C/direct 中央値 | 前半25中央値 | 後半25中央値 | 最小〜最大 | 0.2 ms以上 | C/function_call 中央値・最小〜最大 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.107 | 0.433 | 0.104 | 0.103〜0.514 | 22/50 | 0.386・0.386〜0.440 |
| 2 | 0.106 | 0.139 | 0.102 | 0.096〜0.200 | 1/50 | 0.3905・0.385〜0.455 |
| 3 | 0.1135 | 0.125 | 0.104 | 0.096〜0.185 | 0/50 | 0.387・0.385〜0.423 |
| 4 | 0.113 | 0.113 | 0.113 | 0.113〜0.127 | 0/50 | 0.3965・0.386〜0.521 |
| 5 | 0.2465 | 0.443 | 0.111 | 0.096〜0.575 | 25/50 | 0.387・0.385〜0.687 |

PR #17 の1回目にも前半寄りの遅いサンプルが22件ありましたが、50件中央値は0.107 msでした。5回目は遅い値が中央値付近まで及び、全体中央値は0.2465 msになりました。5回目の後半25件中央値は0.111 msで、C/function_callの中央値も0.387 msでした。5回目のJavaScript中央値は direct 0.4325 / function_call 0.4315 ms、Pythonは direct 18.8755 / function_call 32.7195 msで、C/directと同じ増加は見られませんでした。

新しい10回は `codex/c-sample-stability-investigation` の同じGit HEAD `839630f`、同じ測定ソース・設定で2026-09-24 11:17〜11:18 JSTに実行しました。10回とも成功し保存履歴を再検証。10履歴の45組は `comparable=45`、PR #17 の5履歴も含めた15履歴の105組も `comparable=105` でした。全50サンプルの入力順リストは上記CLIで各履歴から再表示できます。実際の各回のIDとパスは `LOG.md` に記録しています。

| 新回 | C/direct 中央値 | 前半25中央値 | 後半25中央値 | 最小〜最大 | 0.2 ms以上 | C/function_call 中央値（前半 / 後半）・最小〜最大 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.096 | 0.096 | 0.096 | 0.096〜0.113 | 0/50 | 0.386（0.386 / 0.389）・0.385〜0.566 |
| 2 | 0.104 | 0.110 | 0.104 | 0.103〜0.120 | 0/50 | 0.388（0.388 / 0.388）・0.386〜0.436 |
| 3 | 0.295 | 0.387 | 0.239 | 0.111〜0.546 | 43/50 | 0.415（0.426 / 0.395）・0.386〜0.611 |
| 4 | 0.1035 | 0.104 | 0.103 | 0.103〜0.115 | 0/50 | 0.388（0.388 / 0.388）・0.386〜0.422 |
| 5 | 0.105 | 0.104 | 0.111 | 0.103〜0.121 | 0/50 | 0.388（0.388 / 0.388）・0.386〜0.427 |
| 6 | 0.104 | 0.104 | 0.105 | 0.096〜0.148 | 0/50 | 0.419（0.418 / 0.420）・0.403〜0.489 |
| 7 | 0.105 | 0.109 | 0.104 | 0.103〜0.130 | 0/50 | 0.398（0.405 / 0.392）・0.386〜0.446 |
| 8 | 0.104 | 0.104 | 0.104 | 0.104〜0.111 | 0/50 | 0.418（0.418 / 0.418）・0.418〜0.434 |
| 9 | 0.105 | 0.105 | 0.104 | 0.096〜0.121 | 0/50 | 0.393（0.389 / 0.395）・0.385〜0.418 |
| 10 | 0.113 | 0.113 | 0.113 | 0.112〜0.125 | 0/50 | 0.418（0.418 / 0.418）・0.418〜0.437 |

新3回目はC/directの広い区間で値が高く、43/50件が0.2 ms以上でした。一方で最小は0.111 msであり、50件すべてが遅くなったわけではありません。後続のC/function_callは中央値0.415 msでやや高いものの、C/directほどの変化ではありません。同回のJavaScript中央値は0.485 / 0.491 ms、Pythonは19.0825 / 32.5505 msで、同じ大きさの変化は見られません。全10回の他言語の中央値は `LOG.md` に示します。

新3回目の開始前後は電源プランがともに「バランス」、開始前の空き物理メモリ2228.8 MB、プロセス数は前後とも428でした。空きメモリがより少なかった新7回目ではC/direct中央値は0.105 msでした。これらは測定区間外の断面で、CPU使用率・AC給電は未取得です。C/directがC/function_callより先に測られる順序も含め、実行順・端末状態と揺れの因果関係は未確定です。各50サンプルは同一実行内の反復であり独立した50実験ではありません。10回から統計的有意差や最適化効果は宣言しません。次は測定順や端末状態を別の実験計画で切り分けるか判断します。
