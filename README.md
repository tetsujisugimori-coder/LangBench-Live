# LangBench Live

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
