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
  results/
    result.json
  README.md
  LOG.md
```

## 実行方法

```bash
python benchmarks/line_count/python/main.py
```

## 出力されるJSON

`results/result.json` に次の形式で保存されます。

```json
{
  "benchmark_id": "line_count",
  "file": "readingTest.csv",
  "language": "Python",
  "status": "success",
  "rows": 10,
  "elapsed_ms": 1.234
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
