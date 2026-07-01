# LOG

## 2026-07-02 LangBench Live v0.1 初期作成

### 今回変更した概要

* LangBench Live v0.1 として、PythonでCSV行数カウントを行う最小構成を作成した
* `data/readingTest.csv` を読み込み、ヘッダー行を除いたデータ行数を数える処理を作成した
* 処理時間をミリ秒で計測し、ターミナル表示とJSON保存を行う処理を作成した

### 変更したファイル

* `data/readingTest.csv`
* `benchmarks/line_count/python/main.py`
* `results/result.json`
* `README.md`
* `LOG.md`

### 確認した動作

* `python benchmarks/line_count/python/main.py` で実行できること
* CSVのヘッダー行を除いたデータ行数を数えられること
* 処理時間がミリ秒で表示されること
* `results/result.json` が作成または更新されること
* `result.json` に `benchmark_id`, `file`, `language`, `status`, `rows`, `elapsed_ms` が保存されること

### 未対応・今後の検討事項

* C版のベンチマーク追加
* JavaScript版のベンチマーク追加
* 複数言語の結果を同じJSONにまとめる仕組み
* HTMLダッシュボード表示
* 結果表、ランキング、棒グラフ表示
* リアルタイムログ表示
* 過去結果との比較
* 開発現場帳やメモ帳アプリとの連携

## 2026-07-02 LangBench Live v0.1 プロジェクトルート整理

### 今回変更した概要

* 内側の `langbench-live` フォルダに作成された v0.1 用ファイルを、外側の `LANGBENCH-LIVE` 直下へ移動した
* 外側の `LANGBENCH-LIVE` を正式なプロジェクトルートとして扱う構成に整理した
* `python benchmarks/line_count/python/main.py` をプロジェクトルートから実行できることを確認するための整理を行った

### 変更したファイル

* `benchmarks/line_count/python/main.py`
* `data/readingTest.csv`
* `results/result.json`
* `README.md`
* `LOG.md`

### 確認した動作

* `python benchmarks/line_count/python/main.py` で実行できること
* `data/readingTest.csv` を読み込めること
* CSVのヘッダー行を除いたデータ行数を数えられること
* `results/result.json` が作成または更新されること

### 未対応・今後の検討事項

* 今後は新しく `langbench-live` フォルダを作らず、外側の `LANGBENCH-LIVE` 直下をプロジェクトルートとして扱う
* C版のベンチマーク追加
* JavaScript版のベンチマーク追加
* 複数言語の結果を同じJSONにまとめる仕組み
* HTMLダッシュボード表示
