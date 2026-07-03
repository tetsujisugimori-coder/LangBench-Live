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
  results/
    results/
      python_result.json
      javascript_result.json
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

Python版は `results/results/python_result.json`、JavaScript版は `results/results/javascript_result.json` に保存されます。

```json
{
  "benchmark": "csv_line_count",
  "language": "python",
  "samples": [
    {
      "sample": "small",
      "file": "data/readingTest_small.csv",
      "expected_data_rows": 1000,
      "runs": [
        {
          "run": 1,
          "elapsed_ms": 1.234,
          "line_count": 1001
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
