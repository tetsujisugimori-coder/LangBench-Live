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
