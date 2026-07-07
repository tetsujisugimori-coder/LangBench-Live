# LOG

## 2026-07-02 LangBench Live v0.1 初期作成

### 今回変更した概要

* LangBench Live v0.1 として、PythonでCSV行数カウントを行う最小構成を作成した
* `data/readingTest.csv` を読み込み、ヘッダー行を除いたデータ行数を数える処理を作成した
* 処理時間をミリ秒で計測し、ターミナル表示とJSON保存を行う処理を作成した

### 変更したファイル

* `data/readingTest.csv`
* `benchmarks/line_count/python/main.py`
* `results` 配下の結果JSON
* `README.md`
* `LOG.md`

### 確認した動作

* `python benchmarks/line_count/python/main.py` で実行できること
* CSVのヘッダー行を除いたデータ行数を数えられること
* 処理時間がミリ秒で表示されること
* `results` 配下の結果JSONが作成または更新されること
* 結果JSONに `benchmark_id`, `file`, `language`, `status`, `rows`, `elapsed_ms` が保存されること

### 未対応・今後の検討事項

* C版のベンチマーク追加
* JavaScript版のベンチマーク追加
* 複数言語の結果を同じJSONにまとめる仕組み
* HTMLダッシュボード表示

## 2026-07-02 LangBench Live v0.1 CSV生成ファイル整理

### 今回変更した概要

* `tools/create_sample_csv.py` を、`small` / `medium` / `large` の3種類のCSVを固定生成する構成に変更した
* 生成されるサンプルCSVはリポジトリにコミットせず、ローカルで生成する方針をREADMEに追記した
* 生成CSVと結果JSONを `.gitignore` に追加した

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
* `results` 配下の結果JSON
* `README.md`
* `LOG.md`

### 確認した動作

* `python benchmarks/line_count/python/main.py` で実行できること
* `data/readingTest.csv` を読み込めること
* CSVのヘッダー行を除いたデータ行数を数えられること
* `results` 配下の結果JSONが作成または更新されること

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
* 変更内容: small / medium / large の3種類のCSVを対象に、それぞれ3回ずつ `elapsed_ms` と `line_count` を測定し、`summary` とともに結果JSONに保存するように変更。
* 確認コマンド:
  * `python tools/create_sample_csv.py`
  * `python benchmarks/line_count/python/main.py`
* 確認結果:
  * 3種類のCSVについて各3回の測定結果が出力されることを確認。
  * 結果JSONに `samples` 配列、`runs` 配列、`summary` が保存されることを確認。

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
  * Python版の結果ファイルを `results/python_result.json` に保存するようにした。
  * JavaScript版の結果保存先を `results/javascript_result.json` にした。
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

## 2026-07-04 LangBench結果JSON保存先と実行環境メタ情報修正

* 対象: Python版 / JavaScript版の結果JSON出力形式と保存先
* 変更対象ファイル:
  * `benchmarks/line_count/python/main.py`
  * `benchmarks/line_count/javascript/main.js`
  * `README.md`
  * `LOG.md`
* 変更内容:
  * Python版の保存先を `results/python_result.json` に変更した。
  * JavaScript版の保存先を `results/javascript_result.json` に変更した。
  * `created_at`, `execution`, `runtime`, `environment` を結果JSONのトップレベルに保存するようにした。
  * 各 sample に `input_file`, `input_file_size_bytes`, `line_count`, `average_ms`, `median_ms` を追加し、既存の `input`, `runs`, `summary` は維持した。
  * `runner` は `vscode_terminal_powershell`、`runner_label` は `VSCode Terminal / PowerShell` に固定した。
* 確認コマンド:
  * `python benchmarks/line_count/python/main.py`
  * `node benchmarks/line_count/javascript/main.js`
* 確認結果:
  * Python版の実行で `results/python_result.json` が作成・更新されることを確認。
  * JavaScript版の実行で `results/javascript_result.json` が作成・更新されることを確認。
  * 両方の結果JSONに `created_at`, `execution.cwd`, `execution.argv`, `execution.command`, `execution.script_path`, `runtime.version`, `environment.cpu_model`, `environment.cpu_threads`, `environment.memory_total_bytes` が保存されることを確認。
  * 各 sample に `input_file_size_bytes`, `line_count`, `average_ms`, `median_ms` が保存され、既存の `runs`, `summary.average_ms`, `summary.median_ms` が維持されることを確認。
  * Python版の `environment.memory_total_bytes` は標準ライブラリのみでは取得しない方針のため `null` として保存されることを確認。

## 2026-07-04 LangBench結果JSON environment OSキー統一

* 対象: Python版 / JavaScript版の結果JSON `environment`
* 変更対象ファイル:
  * `benchmarks/line_count/python/main.py`
  * `benchmarks/line_count/javascript/main.js`
  * `LOG.md`
* 変更内容:
  * Python版とJavaScript版のOS関連キーを `os_name`, `os_platform`, `os_version` に統一した。
  * Python版は `platform.system()`, `sys.platform`, `platform.version()` を保存するようにした。
  * JavaScript版は `os.platform()` を `os_platform` に保存し、`win32` は `os_name: "Windows"` として保存するようにした。
  * JavaScript版の `os_release` は `os_version` に統一した。
* 確認コマンド:
  * `python benchmarks/line_count/python/main.py`
  * `node benchmarks/line_count/javascript/main.js`
* 確認結果:
  * Python版とJavaScript版の実行で `results/python_result.json` と `results/javascript_result.json` が作成・更新されることを確認。
  * 両方の結果JSONで `environment` に `os_name`, `os_platform`, `os_version`, `cpu_model`, `cpu_threads`, `memory_total_bytes` が保存されることを確認。
  * JavaScript版の結果JSONに `environment.os_release` が出力されないことを確認。

## 2026-07-05 LangBench C版CSV行数カウント追加

### 今回変更した概要

* C版のCSV行数カウント測定コードを `benchmarks/line_count/c/main.c` として追加した
* C版は `fprintf` による手書きJSONで `results/c_result.json` を出力する構成にした
* `small` / `medium` / `large` のCSVを対象に、それぞれ3回ずつ測定する構成にした
* C版の結果JSONには、既存形式に合わせた `samples` と、各測定結果を並べた `results` 配列を保存する構成にした
* CSV行数は既存のPython版・JavaScript版と同じくヘッダー行を含めてカウントする

### 変更したファイル

* `benchmarks/line_count/c/main.c`
* `README.md`
* `LOG.md`

### 測定条件

* コンパイル時間は測定に含めない
* 測定時間はCSV読み込み開始直前から、`fgets` による読み込みと行数カウントが完了した直後までを対象にする
* 測定ごとにCSVファイルを開き直す
* 外部JSONライブラリは使わず、JSONは `fprintf` で出力する

### 確認コマンド

* `gcc benchmarks/line_count/c/main.c -o benchmarks/line_count/c/main.exe`
* `.\benchmarks\line_count\c\main.exe`

### 今後の検討事項

* 将来的にはRUN側でC版のコンパイル、実行、JSON統合を自動化する可能性がある
* `fprintf` でJSONを手書きしているため、将来ファイルパスや任意文字列の項目が増える場合はJSON文字列エスケープ処理を追加する必要がある

## 2026-07-06 JavaScript JIT観察用ベンチマーク追加

### 今回変更した概要

* Node.js / V8 のJIT効果を観察するため、JavaScript版の `jit_numeric_array_sum` ベンチマークを追加した
* CSV読み込みとは別カテゴリのCPU寄りベンチマークとして、`benchmarks/jit_numeric_array_sum/javascript/main.js` を追加した
* 1,000,000件の数値配列を測定前に1回だけ生成し、同じ合計関数を50回実行する構成にした
* 配列生成時間は `setup_ms` として記録し、各iterationの `elapsed_ms` は合計処理のみを対象にした
* warmup専用の捨て回は入れず、1回目から50回目までをそのまま `results` 配列に保存する構成にした
* 計算結果が最適化で消されないように、各iterationの `checksum` を結果JSONに保存する構成にした

### 変更したファイル

* `benchmarks/jit_numeric_array_sum/javascript/main.js`
* `.gitignore`
* `LOG.md`

### 出力

* 出力ファイルは `results/jit_javascript_result.json`
* トップレベルに `language`, `engine`, `benchmark`, `array_size`, `iterations`, `setup_ms`, `results` を保存する
* `engine` には取得できる範囲で Node.js のバージョンと V8 のバージョンを保存する

### 確認コマンド

* `node benchmarks/jit_numeric_array_sum/javascript/main.js`

## 2026-07-06 JavaScript 関数呼び出しJIT観察用ベンチマーク追加

### 今回変更した概要

* 既存の `jit_numeric_array_sum` を元に、関数呼び出しを含むJavaScript数値計算ベンチマーク `jit_function_numeric_sum` を追加した
* CSV読み込みとは別カテゴリのCPU寄りベンチマークとして、`benchmarks/jit_function_numeric_sum/javascript/main.js` を追加した
* 100万件の数値配列を測定前に1回だけ生成し、各iterationで `sumTransformedArray(values)` の実行時間を測定する構成にした
* `sumTransformedArray` では各要素に対して `transformValue(value)` を呼び出し、`value * 2 + 1` の戻り値を合計する
* 配列生成時間は `setup_ms` として記録し、各iterationの `elapsed_ms` は関数呼び出しを含む合計処理のみを対象にした
* 計算結果が最適化で消されないように、各iterationの `checksum` を結果JSONに保存する構成にした

### 変更したファイル

* `benchmarks/jit_function_numeric_sum/javascript/main.js`
* `.gitignore`
* `LOG.md`

### 出力

* 出力ファイルは `results/jit_function_javascript_result.json`
* トップレベルに `language`, `engine`, `benchmark`, `array_size`, `iterations`, `setup_ms`, `results`, `summary`, `environment` を保存する
* `benchmark` と `experiment` は `jit_function_numeric_sum`
* `ARRAY_SIZE` が `1000000` の場合、期待する `checksum` は `1000000000000`

### 確認コマンド

* `node benchmarks/jit_function_numeric_sum/javascript/main.js`

### 確認結果

* `status=success` が表示されることを確認
* `results/jit_function_javascript_result.json` が作成されることを確認
* JSONとして読み取れることを確認
* `results` に50回分のiterationが保存されることを確認
* 各iterationの `checksum` が `1000000000000` になることを確認

## 2026-07-07 JavaScript オブジェクト配列JIT観察用ベンチマーク追加

### 今回変更した概要

* 単純な数値配列と比べて、オブジェクト配列を扱う場合の処理時間変化を観察するため、JavaScript版の `jit_object_numeric_sum` ベンチマークを追加した
* `benchmarks/jit_object_numeric_sum/javascript/main.js` を追加した
* 1,000,000件の `{ value: 数値 }` 形式のオブジェクト配列を測定前に1回だけ生成し、`setup_ms` として記録する構成にした
* 各iterationでは全要素の `value` を合計し、`elapsed_ms` と `checksum` を `results` に保存する構成にした
* `expected_checksum` は `500000500000` とし、checksumが一致しない場合は結果JSONの `status` を `failed` にする構成にした
* 既存のJavaScript JIT系ベンチマークと同じ形式で `engine`, `execution`, `runtime`, `environment`, `summary` を保存する構成にした

### 変更したファイル

* `benchmarks/jit_object_numeric_sum/javascript/main.js`
* `.gitignore`
* `LOG.md`

### 出力

* 出力ファイルは `results/jit_object_javascript_result.json`
* トップレベルに `project`, `benchmark`, `experiment`, `language`, `created_at`, `status`, `engine`, `execution`, `runtime`, `environment`, `output_file`, `array_size`, `iterations`, `setup_ms`, `expected_checksum`, `results`, `summary` を保存する

### 確認コマンド

* `node benchmarks/jit_object_numeric_sum/javascript/main.js`

### 確認結果

* `status=success` が表示されることを確認
* `results/jit_object_javascript_result.json` が作成されることを確認
* JSONとして読み取れることを確認
* `results` に50回分のiterationが保存されることを確認
* 各iterationの `checksum` が `500000500000` になることを確認

## 2026-07-07 Python 関数呼び出し数値合計ベンチマーク追加

### 今回変更した概要

* JavaScript版 `jit_function_numeric_sum` と同じ処理を行うPython版ベンチマークを追加した
* `benchmarks/jit_function_numeric_sum/python/main.py` を追加した
* 1,000,000件の数値配列を測定前に1回だけ生成し、配列生成時間を `setup_ms` として記録する構成にした
* 各iterationでは各要素に対して `transform_value(value)` を呼び出し、`value * 2 + 1` の戻り値を合計する構成にした
* 測定回数は50回とし、各iterationの `elapsed_ms` と `checksum` を `results` に保存する構成にした
* `expected_checksum` は `1000000000000` とし、checksumが一致しない場合は結果JSONの `status` を `failed` にする構成にした
* `summary` に `count`, `average_ms`, `median_ms`, `fastest_ms`, `slowest_ms`, `first_iteration_ms`, `average_ms_excluding_first` を保存する構成にした
* Python標準ライブラリのみを使用する構成にした

### 変更したファイル

* `benchmarks/jit_function_numeric_sum/python/main.py`
* `.gitignore`
* `LOG.md`

### 出力

* 出力ファイルは `results/jit_function_python_result.json`
* トップレベルに `type`, `schema_version`, `project`, `benchmark`, `experiment`, `language`, `created_at`, `status`, `engine`, `execution`, `runtime`, `environment`, `output_file`, `array_size`, `iterations`, `setup_ms`, `expected_checksum`, `results`, `summary` を保存する

### 実行方法

* `python benchmarks/jit_function_numeric_sum/python/main.py`

### 確認コマンド

* `python benchmarks/jit_function_numeric_sum/python/main.py`

### 確認結果

* `status=success` が表示されること
* `results/jit_function_python_result.json` が作成されること
* JSONとして読み取れること
* `results` に50回分のiterationが保存されること
* 各iterationの `checksum` が `1000000000000` になること

## 2026-07-08 C 関数呼び出し数値合計ベンチマーク追加

### 今回変更した概要

* JavaScript版・Python版 `jit_function_numeric_sum` と同じ処理を行うC版ベンチマークを追加した
* `benchmarks/jit_function_numeric_sum/c/main.c` を追加した
* 1,000,000件の64ビット整数配列を測定前に1回だけ生成し、配列生成時間を `setup_ms` として記録する構成にした
* 各iterationでは各要素に対して `transform_value(value)` を呼び出し、`value * 2 + 1` の戻り値を合計する構成にした
* 測定回数は50回とし、各iterationの `elapsed_ms` と `checksum` を `results` に保存する構成にした
* `expected_checksum` は `1000000000000` とし、checksumが一致しない場合は結果JSONの `status` を `failed` にする構成にした
* `summary` に `count`, `average_ms`, `median_ms`, `fastest_ms`, `slowest_ms`, `first_iteration_ms`, `average_ms_excluding_first` を保存する構成にした
* `engine` と `compilation` に `compiler_name`, `compiler_version`, `compile_command`, `optimization_level` を保存する構成にした

### 変更したファイル

* `benchmarks/jit_function_numeric_sum/c/main.c`
* `.gitignore`
* `LOG.md`

### 出力

* 出力ファイルは `results/jit_function_c_result.json`
* トップレベルに `type`, `schema_version`, `project`, `benchmark`, `experiment`, `language`, `created_at`, `status`, `engine`, `execution`, `runtime`, `environment`, `compilation`, `output_file`, `array_size`, `iterations`, `setup_ms`, `expected_checksum`, `results`, `summary` を保存する

### コンパイル方法

* `gcc benchmarks/jit_function_numeric_sum/c/main.c -o benchmarks/jit_function_numeric_sum/c/main.exe`

### 実行方法

* `.\benchmarks\jit_function_numeric_sum\c\main.exe`

### 確認コマンド

* `gcc benchmarks/jit_function_numeric_sum/c/main.c -o benchmarks/jit_function_numeric_sum/c/main.exe`
* `.\benchmarks\jit_function_numeric_sum\c\main.exe`

### 確認結果

* `status=success` が表示されること
* `results/jit_function_c_result.json` が作成されること
* JSONとして読み取れること
* `results` に50回分のiterationが保存されること
* 各iterationの `checksum` が `1000000000000` になること
