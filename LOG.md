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

## 2026-07-02 LangBench Live v0.1 CSV生成ファイル整理

### 今回変更した概要

* `tools/create_sample_csv.py` を、`small` / `medium` / `large` の3種類のCSVを固定生成する構成に変更した
* 生成されるサンプルCSVはリポジトリにコミットせず、ローカルで生成する方針をREADMEに追記した
* 生成CSVと `results/result.json` を `.gitignore` に追加した

### 変更したファイル

* `tools/create_sample_csv.py`
* `README.md`
* `LOG.md`
* `.gitignore`

### 確認した動作

* `python tools/create_sample_csv.py` で `readingTest_small.csv`, `readingTest_medium.csv`, `readingTest_large.csv` を作成できること
* 各CSVのヘッダーが `id,name,category,value,memo` であること
* 標準出力に各ファイル名と行数、最後に `status=success` が表示されること

### 未対応・今後の検討事項

* 生成CSVを使ったベンチマーク対象ファイルの切り替え
* 日本語入りCSVの生成
* 大容量CSVでの測定
* C版、JavaScript版との比較

## 2026-07-02 LangBench Live v0.1 CSV生成スクリプト追加

### 今回変更した概要

* ベンチマーク用CSVを生成する `tools/create_sample_csv.py` を追加した
* `data/readingTest.csv` に、指定した件数分のデータ行を生成できるようにした
* 引数なしの場合は10行、引数ありの場合は指定行数のCSVを生成できるようにした

### 変更したファイル

* `tools/create_sample_csv.py`
* `data/readingTest.csv`
* `README.md`
* `LOG.md`

### 確認した動作

* `python tools/create_sample_csv.py 10` で10行のデータCSVを作成できること
* `python tools/create_sample_csv.py 100000` で100000行のデータCSVを作成できること
* 生成後に `python benchmarks/line_count/python/main.py` を実行し、`rows` が生成したデータ行数と一致すること

### 未対応・今後の検討事項

* 生成データの種類追加
* 日本語入りCSVの生成
* 大容量CSVでの測定
* C版、JavaScript版との比較
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

## 2026-07-02

* 対象: main のCSV読み込みベンチマーク処理
* 変更対象ファイル:
  * `benchmarks/line_count/python/main.py`
  * `LOG.md`
* 変更内容: small / medium / large の3種類のCSVを対象に、それぞれ3回ずつ `elapsed_ms` と `line_count` を測定し、`summary` とともに `result.json` に保存するように変更。
* 確認コマンド:
  * `python tools/create_sample_csv.py`
  * `python benchmarks/line_count/python/main.py`
* 確認結果:
  * 3種類のCSVについて各3回の測定結果が出力されることを確認。
  * `result.json` に `samples` 配列、`runs` 配列、`summary` が保存されることを確認。

## 2026-07-03

* 対象: JavaScript版のCSV行数カウントベンチマーク追加
* 変更対象ファイル:
  * `benchmarks/line_count/python/main.py`
  * `benchmarks/line_count/javascript/main.js`
  * `README.md`
  * `.gitignore`
  * `LOG.md`
* 変更内容:
  * JavaScript版のCSV行数カウントを追加した。
  * Python版 `main.py` に合わせて、`small` / `medium` / `large` を各3回測定する構成にした。
  * Python版の結果ファイルを `results/results/python_result.json` に保存するようにした。
  * JavaScript版の結果保存先を `results/results/javascript_result.json` にした。
  * Node.jsの `fs.createReadStream` と `readline` を使い、CSVをストリームで1行ずつ読み込む方式にした。
  * Python版とJavaScript版の `summary` に `median_ms` を追加した。
* 確認コマンド:
  * `python tools/create_sample_csv.py`
  * `python benchmarks/line_count/python/main.py`
  * `node benchmarks/line_count/javascript/main.js`
* 確認結果:
  * Python版とJavaScript版で `small` / `medium` / `large` の行数が一致することを確認。
  * 各サンプルが3回ずつ測定されることを確認。
  * Python版の結果が `python_result.json` に保存されることを確認。
  * JavaScript版の結果が `javascript_result.json` に保存されることを確認。
  * JavaScript版の実行で `python_result.json` が変更されないことを確認。

## 2026-07-03 LangBench結果JSON共通メタ情報追加

* 対象: Python版 / JavaScript版の結果JSON出力形式
* 変更対象ファイル:
  * `benchmarks/line_count/python/main.py`
  * `benchmarks/line_count/javascript/main.js`
  * `LOG.md`
* 変更内容:
  * LangBench結果JSONに共通メタ情報を追加した。
  * `type: "langbench_result"` を追加した。
  * `schema_version: "1.0"` を追加した。
  * `project: "LangBench Live"` を追加した。
  * `experiment: "csv_line_count"` を追加した。
  * `experiment_label: "CSV行数カウント"` を追加した。
  * Python版とJavaScript版の結果JSON構造をそろえた。
  * samples内を `name`, `input`, `expected.data_rows`, `runs[].metrics.line_count`, `summary` の共通形式に変更した。
* 確認コマンド:
  * `python benchmarks/line_count/python/main.py`
  * `node benchmarks/line_count/javascript/main.js`
* 確認結果:
  * `python_result.json` のルートに `type`, `schema_version`, `project`, `experiment`, `language`, `samples` が保存されることを確認。
  * `javascript_result.json` のルートに `type`, `schema_version`, `project`, `experiment`, `language`, `samples` が保存されることを確認。
  * Python版とJavaScript版で `small` / `medium` / `large` が各3回測定され、`summary.average_ms` と `summary.median_ms` が保存されることを確認。
