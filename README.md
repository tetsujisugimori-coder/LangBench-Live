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

Python版は `results/python_result.json`、JavaScript版は `results/javascript_result.json`、C版は `results/c_result.json` に保存されます。
C版は `fprintf` でJSONを手書きし、既存形式に合わせた `samples` と、各測定をフラットに並べた `results` を出力します。

```json
{
  "type": "langbench_result",
  "schema_version": "1.0",
  "project": "LangBench Live",
  "experiment": "csv_line_count",
  "experiment_label": "CSV行数カウント",
  "language": "python",
  "created_at": "2026-07-03T00:00:00+09:00",
  "status": "success",
  "execution": {
    "runner": "vscode_terminal_powershell",
    "runner_label": "VSCode Terminal / PowerShell",
    "cwd": "C:/Users/...",
    "argv": ["python", "benchmarks/line_count/python/main.py"],
    "command": "python benchmarks/line_count/python/main.py",
    "script_path": "C:/Users/.../benchmarks/line_count/python/main.py"
  },
  "runtime": {
    "name": "python",
    "version": "3.x.x"
  },
  "environment": {
    "os_name": "Windows",
    "os_platform": "win32",
    "os_version": "10.0.x",
    "cpu_model": "Intel(R) Core(TM) ...",
    "cpu_threads": 20,
    "memory_total_bytes": null
  },
  "samples": [
    {
      "name": "small",
      "input": "data/readingTest_small.csv",
      "input_file": "data/readingTest_small.csv",
      "input_file_size_bytes": 12345,
      "line_count": 1001,
      "average_ms": 1.234,
      "median_ms": 1.234,
      "expected": {
        "data_rows": 1000
      },
      "runs": [
        {
          "run": 1,
          "elapsed_ms": 1.234,
          "metrics": {
            "line_count": 1001
          }
        }
      ],
      "summary": {
        "count": 3,
        "average_ms": 1.234,
        "median_ms": 1.234,
        "fastest_ms": 1.000,
        "slowest_ms": 1.500
      }
    }
  ]
}
```

エラーが発生した場合は、`status` が `"error"` になり、可能であれば `message` にエラー内容が保存されます。

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
