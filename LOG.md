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

* 出力ファイルは `results/jit_object_numeric_sum_javascript_result.json`
* トップレベルに `project`, `benchmark`, `experiment`, `language`, `created_at`, `status`, `engine`, `execution`, `runtime`, `environment`, `output_file`, `array_size`, `iterations`, `setup_ms`, `expected_checksum`, `results`, `summary` を保存する

### 確認コマンド

* `node benchmarks/jit_object_numeric_sum/javascript/main.js`

### 確認結果

* `status=success` が表示されることを確認
* `results/jit_object_numeric_sum_javascript_result.json` が作成されることを確認
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

## 2026-07-08 C 関数呼び出し数値合計ベンチマーク コンパイル条件自動記録

### 今回変更した概要

* C版 `jit_function_numeric_sum` の結果JSONに、実際のコンパイル条件を記録できるようにした
* 当初は `LANGBENCH_OPTIMIZATION_LEVEL` と `LANGBENCH_COMPILE_COMMAND` をgccの `-D` で渡す方式を試したが、PowerShell、gcc、Cプリプロセッサ間の引用符エスケープが壊れやすいため廃止した
* `run_benchmark.ps1` がgccを引数配列で実行し、ベンチマーク実行後に結果JSONを読み込んで `engine` と `compilation` の `compile_command` と `optimization_level` を更新する構成にした
* PowerShell用の `benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1` を追加した
* スクリプトは `none`, `O0`, `O1`, `O2`, `O3` を受け取り、gccの最適化オプションと結果JSONの記録へ反映する
* コンパイル失敗時は `main.exe` を実行せず、`main.exe` 失敗時は結果JSONを更新しない構成にした
* JSON更新後に再読込し、記録した `compile_command` と `optimization_level` を検証する構成にした
* 更新後のJSONはUTF-8 BOMなしで保存し、既存のJSON取り込み処理で読み込めるようにした

### 変更したファイル

* `benchmarks/jit_function_numeric_sum/c/main.c`
* `benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1`
* `LOG.md`

### 使用方法

* 最適化なし: `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel none`
* O0: `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel O0`
* O1: `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel O1`
* O2: `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel O2`
* O3: `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel O3`

### 確認コマンド

* `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel none`
* `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel O0`
* `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel O1`
* `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel O2`
* `powershell -ExecutionPolicy Bypass -File benchmarks/jit_function_numeric_sum/c/run_benchmark.ps1 -OptimizationLevel O3`

### 確認結果

* `none` で実行した結果JSONに `optimization_level: "none"` が記録されることを確認
* `none` で実行した結果JSONの `compile_command` に最適化オプションが含まれないことを確認
* `O0`, `O1`, `O2`, `O3` で実行した結果JSONに、それぞれ `optimization_level: "O0"`, `"O1"`, `"O2"`, `"O3"` が記録されることを確認
* `O2` で実行した結果JSONに `optimization_level: "O2"` が記録されることを確認
* `O2` の結果JSONの `compile_command` に `-O2` が含まれることを確認
* `O3` の結果JSONの `compile_command` に `-O3` が含まれることを確認
* `engine` と `compilation` の `compile_command` と `optimization_level` が一致することを確認
* JSONとして読み取れることを確認
* checksum mismatch が0件であることを確認
* `results` が50件保持され、`summary` が保持されることを確認
* 今回の確認実行では `summary.average_ms` が `none: 1.364`, `O0: 1.373`, `O1: 0.419`, `O2: 0.416`, `O3: 0.436` となり、`O2` と `O3` の測定時間に差が出ることを確認

## 2026-07-09 数値配列合計ベンチマーク Python/C版追加

### 変更内容

* `jit_numeric_array_sum` にPython版とC版を追加した
* C版を `-O2 -std=c11 -Wall -Wextra` でビルドするPowerShellランナーを追加した
* PowerShell側でGCCプロセスのコンパイル時間だけを計測し、C結果の `build.compile_ms` に記録した
* Python版、C版、JavaScript版に共通の `build` 項目を追加した
* Cの合計値には、32ビット整数の範囲を超える `499999500000` を安全に保持するため `int64_t` を使用した
* JavaScript版の偶数件の中央値を、ソート後の中央2件の平均へ修正した
* Python版とC版も同じ中央値計算を使用する

### 実行確認

* Python版、C版、JavaScript版がすべて `status=success` で終了した
* 各結果の `array_size` は1000000、`iterations` と `results` 件数は50だった
* 全言語の全反復で `checksum` が `499999500000` と一致した
* Python版とJavaScript版の `compile_ms` は `null`、C版は数値になった
* C版はコンパイラ警告なしでビルドされた
* 確認時のCコンパイル時間は `758.492 ms` だった

### 生成JSON

* `results/jit_numeric_array_sum_python_result.json`
* `results/jit_numeric_array_sum_c_result.json`
* `results/jit_numeric_array_sum_javascript_result.json`

## 2026-07-09 数値配列合計ベンチマーク 総合所要時間追加

### 変更内容

* 3言語をJavaScript、Python、Cの順に実行する共通PowerShellランナーを追加した
* PowerShellから見たプロセス全体の所要時間を `timing.process_total_ms` に追加した
* 50件の `results[].elapsed_ms` の実測値合計を `timing.benchmark_total_ms` に追加した
* 既存の配列生成時間を `timing.setup_ms` にも記録し、ルートの `setup_ms` は互換性のため維持した
* C版ではコンパイルと実行を分離し、合計を `timing.build_and_process_total_ms` に追加した
* Python版とJavaScript版の `timing.build_and_process_total_ms` は `null` とした

### 実行確認

* `benchmarks/jit_numeric_array_sum/run_all.ps1` から3言語を順次実行した
* 3言語の `process_total_ms` が数値であることを確認した
* 各言語の `timing.setup_ms` がルートの `setup_ms` と一致することを確認した
* 各言語の `timing.benchmark_total_ms` が50件の実測値合計と一致することを確認した
* C版だけ `build_and_process_total_ms` が数値であることを確認した
* 全150件の `checksum` が `499999500000` と一致することを確認した
* C単独ランナーから実行した場合も、C結果JSONの `timing` を更新するようにした

## 2026-07-09 C版 初回・再実行時間の分離

### 変更内容

* C版を1回コンパイルし、生成された同じ実行ファイルを再コンパイルせず2回実行するようにした
* コンパイル直後の初回実行時間を `timing.first_process_total_ms` に追加した
* 同じ実行ファイルの再実行時間を `timing.repeat_process_total_ms` に追加した
* コンパイル時間と初回実行時間の合計を `timing.build_and_first_process_total_ms` に追加した
* C版の旧 `timing.process_total_ms` と `timing.build_and_process_total_ms` は、意味を明確にするため新項目へ置き換えた

### 実行確認

* `c/run_c.ps1` の単独実行でコンパイルと2回のプロセス実行が成功することを確認した
* 初回と再実行が同一の `main.exe` を使用し、間に再コンパイルがないことを確認した
* 最終JSONが2回目の実行結果であり、全50件のchecksumが `499999500000` と一致することを確認した
* `build_and_first_process_total_ms` が `compile_ms + first_process_total_ms` と一致することを確認した
* `benchmark_total_ms` が2回目の50件の `elapsed_ms` 合計と一致することを確認した
* 初回と再実行の差は、実行ファイル起動時のOSキャッシュやセキュリティ検査などを含む外部要因として観測できる

## 2026-08-01 LangBench結果JSON正式仕様統一

### 目的

* C・Python・JavaScriptの `jit_object_numeric_sum` 結果をMemo Nexusから自動取込・比較・グラフ表示できる共通構造へ統一した
* 言語ごとの差分を抑えるため、ルートキーの名前、型、順序と、取得不能値の `null` 表現を統一した

### 仕様変更

* ルートキーを `type`, `schema_version`, `project`, `benchmark`, `experiment_id`, `run_id`, `language`, `created_at`, `status`, `engine`, `execution`, `environment`, `config`, `timing`, `results`, `validation`, `error` の順へ統一した
* 重複していた `experiment` を新規出力から廃止し、処理名を `benchmark: "jit_object_numeric_sum"` に統一した
* `experiment_id` を3言語共通の `YYYYMMDD_HHMMSS_<benchmark>`、`run_id` を各起動固有の `YYYYMMDD_HHMMSS_<language>_<benchmark>` と定義した
* 1回のプログラム起動を1 runとし、50回の内部測定を `results.samples_ms` に格納した
* `array_size` を `config.item_count`、`iterations` を `config.measurement_iterations` へ変更した。測定件数50、ウォームアップ5、計算内容は変更していない
* `timing` を `process_startup_ms`, `setup_ms`, `warmup_ms`, `measurement_ms`, `benchmark_total_ms` へ統一した
* `measurement_ms` を `samples_ms` の合計、`benchmark_total_ms` をsetup・warmup・measurementの合計とした。JSON生成・保存時間と環境情報取得時間は含めない
* `results` を `samples_ms`, `min_ms`, `max_ms`, `mean_ms`, `median_ms` へ統一し、偶数件の中央値は中央2値の平均とした
* 1回分のchecksum、期待値、許容誤差、判定結果を `validation` へまとめた。各反復でも期待値との一致を確認する
* 成功時は `error: null`、Python・JavaScriptで安全に結果化できる失敗時は `status: "error"` と `error.type` / `error.message` を出力する
* Cの取得不能なOSバージョンなどは `unknown` や0ではなく `null` とした
* 結果ファイル名は既存の `jit_object_numeric_sum_<language>_result.json` を維持した

### IDと共通ランナー

* `benchmarks/jit_object_numeric_sum/run_all.ps1` を追加し、1つの `experiment_id` をPython、JavaScript、Cへ渡すようにした
* C単独ランナーも `ExperimentId` と `RunId` を受け取れるようにした
* ユーザーの既存未追跡 `main.exe` を上書きしないよう、Cランナーは一時EXEを生成して実行後に削除する

### 後方互換

* `tools/validate_result_json.py` に正式JSONの検証と旧結果の正規化処理を追加した
* `samples` → `samples_ms`、`min` / `max` / `mean` / `median` → `_ms`付きキー、`iterations` / `repeat_count` → `measurement_iterations`、`array_size` / `object_count` / `data_size` → `item_count`、`total_ms` → `benchmark_total_ms`、旧ルートまたは反復内 `checksum` → `validation.checksum`、`experiment` → `benchmark` の読替に対応した
* 新しく生成するJSONには旧キーを出力しない

### 変更したファイル

* `benchmarks/jit_object_numeric_sum/python/main.py`
* `benchmarks/jit_object_numeric_sum/javascript/main.js`
* `benchmarks/jit_object_numeric_sum/c/main.c`
* `benchmarks/jit_object_numeric_sum/c/run_c.ps1`
* `benchmarks/jit_object_numeric_sum/run_all.ps1`
* `tools/validate_result_json.py`
* `tests/test_result_schema.py`
* `results/jit_object_numeric_sum_python_result.json`
* `results/jit_object_numeric_sum_javascript_result.json`
* `results/jit_object_numeric_sum_c_result.json`
* `README.md`
* `LOG.md`

### 実行したテストと結果

* `python benchmarks/jit_object_numeric_sum/python/main.py --experiment-id=... --run-id=...`: 成功
* `node benchmarks/jit_object_numeric_sum/javascript/main.js --experiment-id=... --run-id=...`: 成功
* `gcc benchmarks/jit_object_numeric_sum/c/main.c -O2 -std=c11 -Wall -Wextra -o <一時EXE>`: 警告なしで成功
* 一時EXEへ共通 `experiment_id` / C用 `run_id` を渡した実行: 成功
* `powershell -NoProfile -ExecutionPolicy Bypass -File benchmarks/jit_object_numeric_sum/run_all.ps1 -ExperimentId 20260801_130000_jit_object_numeric_sum`: 3言語と検証が成功
* `python -B tools/validate_result_json.py` に3結果JSONを指定: `validated=3`
* `python -B -m unittest discover -s tests -v`: 3件成功
* `node --check benchmarks/jit_object_numeric_sum/javascript/main.js`: 成功
* `git diff --check`: 成功
* 全言語で `samples_ms` 50件、`measurement_ms` とサンプル合計、`benchmark_total_ms` と3区間合計、checksum `500000500000`、`validation.passed: true`、成功時 `error: null` を確認した
* 指定された既存未追跡ファイル群はテスト前後のSHA-256集約値が一致し、内容が変更されていないことを確認した

### 未確認事項・残課題

* C版は結果ファイルを開く前に発生する初期化・メモリ確保・タイマー取得エラーでは、安全なエラーJSONを保存できないため標準エラー出力のみとなる
* `process_startup_ms` は対象プログラム内から正確に取得できないため、3言語とも `null` とした
* CのOSバージョンは信頼できるAPIで取得していないため推測せず `null` とした
* Memo Nexusへの実取り込みは接続先がこのリポジトリにないため未確認

## 2026-08-21 function_call_numeric_sum

* C・Python・JavaScriptに `function_call_numeric_sum` を追加した。入力は1から1,000,000、期待合計は500000500000、各ケースはwarmup 5回・本測定50回である。
* `direct` はループ内の直接加算、`function_call` はループ外の `add` 呼び出しによる加算で、配列生成はsetup、両ケースのwarmupとmeasurementを個別に計測する。
* JSON正式仕様1.0をベンチマーク固有の2ケース結果へ拡張し、`results.direct`/`results.function_call`、両checksum、各統計値を検証器で検証する。
* CはMSVC/GCC/Clangのnoinline属性で加算関数のインライン化を抑制する。V8のJIT最適化、CPythonの通常関数呼び出し、非対応Cコンパイラでは呼び出し保持を保証できない点が既知の制約である。
* 変更: ベンチマーク実装・ランナー、JSON検証器、README、`.gitignore`。`run_all.ps1`、JSON検証、既存ユニットテスト、JavaScript構文検査を実行し成功した。

### PR #5 レビュー修正

* C版はランナーから渡される実測のコンパイル時間、GCCバージョン、コンパイルコマンド、ソースパスを検証して `build` へ保存するよう修正した。
* Cの日時、cwd、argv、CPU、アーキテクチャ、論理プロセッサ数、メモリ容量を実行時に取得し、setupには配列の確保と初期化の両方を含めるよう修正した。
* 結果検証器は共通検証を先に実行し、IDとベンチマークの対応、ビルド、有限数、時刻、統計・timing・checksumを検証する。関数呼び出しベンチマーク固有の2ケース形状はその後に検証する。
* 不正な関数呼び出し結果（ID、build、ケース形状、NaN、checksum）を拒否するユニットテストを追加した。

### PR #5 再レビュー回帰修正

* レガシーJSON正規化の候補キー、0値保持、空配列の安全な処理を復元した。
* 正式なエラー結果で統計・timing・validationの必須キーとnull値を厳密に検証するよう復元した。
* C版でJSONストリームエラーと `fclose` の失敗を検出し、成功時だけ成功状態を出力するようにした。
* 複数結果JSONの不一致・重複言語・読取失敗をCLI経路で確認する回帰テストを追加した。

## 2026-08-01 PR #3 レビュー指摘対応

### レビューで発見された問題

* 正式なエラーJSONは `config.measurement_iterations: 50` と `results.samples_ms: []` を出力するが、検証器がstatusを区別せず件数一致を要求していたため必ず不合格になっていた
* `run_id` は秒単位のため、同じ言語・ベンチマークを同一秒内に複数回起動すると重複し得る性質が明文化されていなかった
* Cランナーから渡すコンパイル時間、コンパイラバージョン、コンパイルコマンド、ソースパスをC実装が正式JSONへ保持していなかった

### エラーJSON検証

* `status: "success"` では、サンプル件数、`measurement_ms`、min/max/mean/median、`benchmark_total_ms`、checksum、`validation.passed: true`、`error: null` を検証する
* `status: "error"` では反復数とサンプル件数の一致を要求せず、空の `samples_ms`、nullの統計・timing、`validation.passed: false`、空でない `error.type` / `error.message` を検証する
* Python版とJavaScript版が生成する正式エラー構造を模した正常系テストを追加した
* `error: null`、`validation.passed: true`、サンプル混入、空のerror type/messageを拒否する異常系テストを追加した

### 任意のbuildセクション

* 正式ルートキーの `environment` と `config` の間へ `build` を追加した
* PythonとJavaScriptは `build: null` とする
* Cは `required`, `compiler`, `compiler_version`, `compile_command`, `compile_ms`, `source_path` を持つオブジェクトを出力する
* Cの `engine` は `runtime` と `runtime_version` のみに整理し、コンパイラ情報は `build` へ集約した
* 検証器はCの各build値と非負の `compile_ms` を検証し、言語間ルート型比較では仕様上型が異なる `build` だけを除外する

### run_id

* 形式 `YYYYMMDD_HHMMSS_<language>_<benchmark>` と生成処理は変更していない
* 各起動を識別する秒単位の補助IDであり、同一秒内に重複し得るため単独のDB一意キーにしないことをREADMEへ追記した
* 永続保存では `experiment_id`, `run_id`, `language`, `created_at`, 取込側IDなどを組み合わせる

### 不要フォルダ

* `font-comparison/` がGit未追跡であることを確認し、明示された削除許可に基づいて3ファイルを含むフォルダを削除した
* `.gitignore` には追加していない

### 変更ファイル

* `README.md`
* `LOG.md`
* `benchmarks/jit_object_numeric_sum/python/main.py`
* `benchmarks/jit_object_numeric_sum/javascript/main.js`
* `benchmarks/jit_object_numeric_sum/c/main.c`
* `tools/validate_result_json.py`
* `tests/test_result_schema.py`
* `results/jit_object_numeric_sum_python_result.json`
* `results/jit_object_numeric_sum_javascript_result.json`
* `results/jit_object_numeric_sum_c_result.json`

### 実行したテストと結果

* `python -B -m unittest discover -s tests -v`: 5件成功
* `node --check benchmarks/jit_object_numeric_sum/javascript/main.js`: 成功
* `gcc benchmarks/jit_object_numeric_sum/c/main.c -O2 -std=c11 -Wall -Wextra -o <一時EXE>`: 警告なしで成功
* `powershell -NoProfile -ExecutionPolicy Bypass -File benchmarks/jit_object_numeric_sum/run_all.ps1`: 3言語実行成功
* `python -B tools/validate_result_json.py` に3結果JSONを指定: `validated=3`
* `git diff --check`: 成功
* Python・JavaScriptの `build` がnull、Cのbuild情報が揃い `compile_ms` が0以上であることを確認した
* 3言語の共通 `experiment_id`、正式形式の `run_id`、50サンプルとtiming・checksum整合性を確認した
* 他の既存未追跡ファイルはテスト前後のSHA-256が一致し、変更されていないことを確認した

### 残課題・未確認事項

* `run_id` は仕様どおり単独では一意でないため、Memo Nexusなどの取込側で複合識別を実装する必要がある
* Memo Nexusへの実取り込みは接続先がこのリポジトリにないため未確認

## 2026-09-01 PR #7 レビュー指摘対応

* 保存済み解析資料の結論を無条件で現在の結果へ適用していた問題を修正した。
* `artifacts/function-call-analysis/manifest.json` と結果JSONの `provenance` に、ソースSHA-256、処理系名・バージョン、CPUアーキテクチャ、主要オプション、解析ID・日時、現在条件、照合結果、不一致項目を追加した。
* CはGCCバージョン、x64、`-O2 -std=c11 -Wall -Wextra`、ソースハッシュが一致した場合だけ、対象addの非インライン化、directループのベクトル化、SSE2を採用する。不一致時は保存済み判定を `not_checked` へ降格する。
* PythonはCPythonのバイトコード解析を処理系・バージョン・アーキテクチャ・最適化レベル・ソースが一致した場合だけ使用する。CPython以外や条件不一致ではインライン化とベクトル化を `not_checked` にする。
* PythonのJIT判定を純粋にテスト可能な関数へ分離し、`sys._jit.is_available()` と `is_enabled()` を区別した。JIT非搭載は `not_applicable`、搭載済み無効は `not_detected`、搭載・有効だが対象コードの作動が未確認なら `unknown`、API失敗は `unknown` とする。
* JavaScriptはV8バージョン、アーキテクチャ、ソース、`process.execArgv`と`NODE_OPTIONS`由来のオプションを照合する。`--jitless`等がある場合、過去のJIT・インライン化判定を使用しない。
* バリデーターへprovenance条件の再比較、JITのapplicable整合、SIMDのresult/isa整合、ISA重複禁止、根拠なしの確定判定禁止、不一致provenanceでの確定判定禁止、manifest構造検証を追加した。`optimization_analysis`を持たない既存schema 1.0 JSONは引き続き有効である。
* `tools/generate_function_call_analysis.ps1` で、最終ソースからGCCレポート、Cアセンブリ、Pythonバイトコード、V8トレース、manifestを再生成した。V8の標準出力と標準エラーは別々に収集し、区切って保存した。

### テスト結果

* `python -m unittest discover -s tests -v`: 14件成功
* `node tests/test_javascript_optimization_analysis.js`: 5件成功
* `python -m py_compile benchmarks/function_call_numeric_sum/python/main.py tools/validate_result_json.py`: 成功
* `node --check benchmarks/function_call_numeric_sum/javascript/main.js`: 成功
* `benchmarks/function_call_numeric_sum/run_all.ps1`: C・Python・JavaScriptの実行と3結果の検証が成功（`validated=3`）
* `node --jitless benchmarks/function_call_numeric_sum/javascript/main.js`: 成功し、`provenance.status: mismatched`、`mismatches: ["options"]`、JITとインライン化が `not_checked` になることを確認
* 通常条件へ戻した3結果の明示検証: `validated=3`

## 2026-09-01 PR #7 2回目レビュー指摘対応

* 条件一致時の最適化結論が実行コード内の固定値だったため、異なるアーキテクチャで成果物を再生成すると解析内容に関係なく過去の結論を出せる問題を修正した。
* manifestの各言語エントリーへ `findings` を追加し、結果JSONの `provenance.artifact_findings` から保存値と現在値の対応を検証できるようにした。
* `tools/extract_function_call_findings.py` を追加し、CはGCCレポートと対象関数のアセンブリ、Pythonは対象コードオブジェクトのバイトコード、JavaScriptは対象関数名を含むV8トレースから結論を抽出するようにした。
* CのSSE2はx86系アーキテクチャかつ `direct_sum` の対応命令を確認した場合だけ記録し、ARM64や命令未確認時は `not_checked` にする。
* C、Python、JavaScriptでmanifestエントリーの構造を利用前に検証し、欠落、型不正、構文エラー、対象言語なしを `unavailable` として測定を継続するようにした。
* バリデーターを不正な `applies_to`、condition、implementation、options、findingsに対して型安全にし、条件一致時の現在値と保存済みfindingsの一致、不一致時の `not_checked`、利用不能時の `unknown` を検証するようにした。
* manifest専用CLI `python tools/validate_result_json.py --manifest ...` を追加した。

### テスト結果

* `python -m unittest discover -s tests -v`: 19件成功
* `node --test tests/test_javascript_optimization_analysis.js`: 12件成功
* `tests/test_c_optimization_analysis.ps1`: 7件成功
* PythonとJavaScriptの構文検査: 成功
* Windows PowerShell 5.1で解析資料4件とfindings付きmanifestの再生成: 成功
* manifest検証: `validated_manifest=1`
* 3言語の実行と結果検証: `validated=3`
* `node --jitless`で保存済みfindingsが `not_checked` へ降格することを確認し、通常条件の結果へ復元した。

## 2026-09-01 PR #7 3回目レビュー指摘対応

* Python・JavaScript・Cのランナーが対象言語entryだけを検証し、manifestルートや兄弟言語entryの不正を見逃していた問題を修正した。
* manifest文書全体の検証と各言語entryの詳細検証を分離し、ルートキー、schema 1.0、解析ID、タイムゾーン付き日時、3言語の完全なキー集合と全entryを検証するようにした。
* entryの `generation_commands` と厳密なevidence構造も検証し、`tools/validate_result_json.py --manifest` とランナーの受理・拒否条件を揃えた。
* 存在するmanifestの構文・構造不正は `manifest_invalid`、ファイル不在は `manifest_unavailable` と区別した。不正時は解析メタデータと保存済みfindingsをnullにし、対象判定を `unknown`、SIMD ISAとevidenceを空配列として測定を継続する。
* schema 2.0、analysis_id欠落、不正なgenerated_at、languagesの配列・null、兄弟言語欠落、未知ルートフィールド、正常manifestをPython・JavaScript・Cで回帰テストした。
* 最終ソースから `tools/generate_function_call_analysis.ps1 -AnalysisId function-call-analysis-20260901-review3` でPythonバイトコード、V8トレース、manifestを再生成した。C解析資料は再生成後も内容差分がなかった。

### テスト結果

* `python -m unittest tests.test_result_schema`: 20件成功
* `node --test tests/test_javascript_optimization_analysis.js`: 20件成功
* `tests/test_c_optimization_analysis.ps1`: 14件成功
* `python tools/validate_result_json.py --manifest artifacts/function-call-analysis/manifest.json`: `validated_manifest=1`
* `python -m unittest discover -s tests -v`: 20件成功
* Python・JavaScript構文検査: 成功
* `node --jitless benchmarks/function_call_numeric_sum/javascript/main.js`: `mismatched`、JIT・対象findingsの `not_checked` を確認
* `benchmarks/function_call_numeric_sum/run_all.ps1`: C・Python・JavaScriptの通常実行と3結果の検証が成功（`validated=3`）

## 2026-09-24 実験条件の定義と履歴への保存

* `experiments/function_call_numeric_sum.json` に対象言語、測定設定、期待checksumを定義した。各言語の既存測定処理と結果schema 1.0は変更していない。
* 履歴保存前に定義の構造・期待checksum・3言語の実測設定との一致を確認する。失敗時は履歴フォルダを作成しない。
* 成功時は使用した定義を `experiment.json` として各履歴にコピーし、`archive.json` にSHA-256を記録する。保存の一意IDには既存の `archive_id` を使う。
* 次の段階は保存済み定義に加えて処理系・環境条件を照合し、履歴間の比較可能性を判定すること。定義だけを変更して実測条件を変える機能はまだない。

### 確認結果

* `python -m unittest tests.test_result_schema.ArchiveResultsTests -v`: 3件成功。定義との不一致を保存前に拒否し、保存した定義とハッシュの一致も確認した。
* `python -m py_compile tools/archive_results.py` と `git diff --check`: 成功。
* `python tools/validate_result_json.py` に追跡済み3言語結果を渡して `validated=3`。
* `python -m unittest discover -s tests -v`: 23件実行し、既存の解析manifest対現在ソースSHA-256照合に関する3言語のsubtestだけ失敗。PR #8から継続する既知の不一致で、解析資料の再生成なしに保存済みハッシュは変更していない。
* この環境ではWindows用のC実行とPowerShell統合実行は未確認。

### 2026-09-24 Windowsでの追加検証

* `python -B -m unittest tests.test_result_schema.ArchiveResultsTests -v`: 3件成功。定義の不一致で履歴を作らず、再実行時に両方の履歴が残ることを確認した。
* `pwsh -NoProfile -File benchmarks/function_call_numeric_sum/run_all.ps1`: Python・JavaScript・Cの統合実行と`validated=3`が成功し、`results/history/20260924_032155_function_call_numeric_sum/863c1aed3a874301a647f44c794fff25/`を作成した。
* 保存された`experiment.json`と3言語の結果を読み戻した。`archive.json`に記録された4件のSHA-256がすべて実ファイルと一致し、保存結果の再検証も`validated=3`となった。
* `node --test tests/test_javascript_optimization_analysis.js`: 20件成功。
* `python -B -m unittest discover -s tests -v`: 23件中、解析manifestの保存済みソースSHA-256と現行ソースの不一致に対応するC・Python・JavaScriptの3 subtestが失敗し、他は成功した。`pwsh -NoProfile -File tests/test_c_optimization_analysis.ps1`も同じ不一致で`valid C manifest did not match`となった。解析成果物を再生成せずにSHA-256だけ変更していない。

## 2026-09-24 function_call_numeric_sumの結果履歴保存

* 既存schema 1.0と各言語の測定処理は維持し、3件の結果検証後に `results/history/<experiment_id>/<archive_id>/` へ元のJSONを追記保存する。
* `archive.json` にarchive ID、元のrun ID、SHA-256、保存日時を記録する。異なるexperiment ID、重複言語、不正なJSON、Validator不合格の結果は保存しない。
* 既存の固定名出力ファイルは実行中の一時的な置き場として残し、`run_all.ps1` 同士の同時実行をロックで防ぐ。履歴はGitの管理対象外にする。

### 確認結果

* 履歴保存の2件の回帰テストが成功。再実行で前回の3結果が維持され、不一致や不正値では履歴が作成されない。
* 追跡済みの3言語結果は現行Validatorで `validated=3`。
* Linux環境での全Pythonテスト22件中、解析manifest整合テストのC・Python・JavaScriptに対応する3つのsubtestが失敗。保存済みSHA-256が現在のmainのソースと一致しない。今回の変更対象外であり、解析成果物を検証せずにハッシュだけ書き換えることはしない。
* Windows専用のC実行とPowerShellの統合実行はローカルLinux環境では未実施。

### 2026-09-24 Windowsでの追加検証

* `pwsh -NoProfile -File benchmarks/function_call_numeric_sum/run_all.ps1` でPython・JavaScript・Cの統合実行が成功し、`validated=3` の後に `results/history/20260924_020315_function_call_numeric_sum/645802ee42c5428796463f3b25f8f978/` を作成した。
* 保存された3件のJSONを読み戻し、`archive.json` のSHA-256と各ファイルの実測値がすべて一致すること、および保存ファイルを現行Validatorに渡して `validated=3` となることを確認した。
* `python -m unittest tests.test_result_schema.ArchiveResultsTests -v` は2件成功。`python -m unittest discover -s tests -v` は22件を実行し、履歴保存の2件を含む他のテストは成功した。解析manifestの保存済みソースSHA-256と現在のソースが一致しない既存の3つのsubtest（C・Python・JavaScript）は引き続き失敗する。

## 2026-09-24 PR #9 最適化解析の根拠再生成と履歴の再検証

### 原因

* 修正前のmainとPR #9で、Python全体テストはそれぞれ22件中3言語のsubtest、23件中3言語のsubtestが失敗した。C解析テストも両ブランチで`valid C manifest did not match`となった。
* 解析manifestに保存された3言語の`source_sha256`は、現行ソースのGit保存バイト列と一致しなかった。Windowsの`core.autocrlf=true`は作業ツリーの3ソースをCRLFに変え、生バイトをハッシュするテストとランナーにさらに別の値を与えていた。Cランナーの不一致項目は`source_sha256`だけで、GCCの版・アーキテクチャ・オプションは一致していた。古いハッシュの生成時点の未コミット状態までは特定できていない。

### 変更

* `.gitattributes`で対象3ソースと解析資料をLF改行に固定した。`tools/generate_function_call_analysis.ps1`はリポジトリを作業ディレクトリとして相対ソースパスでGCC・Python・Node.jsを起動し、作業ツリーの場所を資料に埋め込まないようにした。
* 現行ソースからGCCレポート・アセンブリ、Pythonバイトコード、V8トレースを実行して得た。アセンブリは再生成後も内容差分がなく、残る資料と`manifest.json`を更新した。`README.md`の解析例と生成・ハッシュ条件も更新した。
* `tests/test_result_schema.py`で、実資料から再抽出した3言語の`findings`とmanifestとの一致、および期待checksumが定義と異なる結果を保存前に拒否することを検査した。結果schema 1.0と測定ループは変更していない。

### 実測した確認

* Windows PowerShell 5.1で生成スクリプトをリポジトリ外の作業ディレクトリから実行し、`analysis_id=function-call-analysis-20260924-pr9-rebuild`で成功した。manifest構造検証は`validated_manifest=1`。3ソースの実測SHA-256がmanifestと一致し、GCC・Python・V8資料から再抽出した`findings`も各言語で一致した。
* `python -B -m unittest discover -s tests -v`: 23件すべて成功。`node --test tests/test_javascript_optimization_analysis.js`: 20件すべて成功。`pwsh -NoProfile -File tests/test_c_optimization_analysis.ps1`: 14件すべて成功。
* `python -B -m unittest tests.test_result_schema.ArchiveResultsTests -v`: 3件成功。定義と設定・期待checksumが異なる場合、履歴フォルダが作成されないことを確認した。
* `pwsh -NoProfile -File benchmarks/function_call_numeric_sum/run_all.ps1`: C・Python・JavaScriptの統合実行が成功し、`validated=3`の後に`results/history/20260924_034054_function_call_numeric_sum/7dcea74c253543bf908974c60a66bb95/`を作成した。保存された`experiment.json`は定義原本とバイト単位で一致し、`archive.json`に記録された定義1件と結果3件のSHA-256はすべて読み戻し値と一致した。保存結果の再検証は`validated=3`、3言語の解析provenanceは`matched`だった。
* コミット`b2d5bff`から新規worktreeを作成し、3ソースのCRLFがいずれも0件で実測SHA-256がmanifestと一致することを確認した。そのチェックアウトでmanifestと資料のPythonテスト1件、C解析テスト14件が成功した。

### 残る確認範囲

* この再生成と統合実行はWindows、GCC 16.1.0、CPython 3.14.7、Node.js 24.20.0 / V8 13.6.233.17-node.53で確認した。他の処理系・バージョン・アーキテクチャでの資料再生成や統合実行は未実施で、条件不一致時は保存済み解析結論を適用しない。

## 2026-09-24 PR #9 既存Windows作業ツリーの改行と解析ハッシュ

### 原因と再現

* `core.autocrlf=true` の一時worktreeで `origin/main` (`a264782`) からPR先端へ `git switch --detach` で通常更新した。更新前のC・Python・JavaScriptソースのCRLF件数は順に191・230・21件、生バイトSHA-256は `66de6d87…`・`fe6aef96…`・`cbbebeae…`、旧manifestは `3c2ef4d2…`・`21608363…`・`081a8d31…` で、Pythonの3言語照合subtestがすべて失敗した。
* 先行PR先端 (`ae7c39d`) への通常更新では3ソースのGit blobが変わらず、`.gitattributes` の `eol=lf` が追加されても実ファイルはC・Python・JavaScriptともCRLFのままだった。`git ls-files --eol` は `i/lf w/crlf attr/text eol=lf` を示し、Pythonの3言語照合subtestとC解析テストは失敗した。Gitは属性が変わっただけの既存・未変更ファイルを書き直さない。新規チェックアウトでLFになることは、既存作業ツリーの修復を証明しない。
* 修正コミット `9a622b4` へmainから通常更新すると、変更のないCソースはCRLF 191件のまま、生バイトSHA-256 `66de6d87e593e3beeb8b45c2ddd6954faa2cec0a4262836435460979eb9d0e0b` のままだった。PythonとJavaScriptは今回の実装変更によりGitが書き直してLFになった。3言語ともCRLFになる条件も一時複製で追加検証した。

### 採用した定義と変更

* `source_sha256` を「解析・実行それぞれの実ファイルのバイト列からCRLFペアだけをLFに変換し、残りのバイトを変えずに計算したSHA-256」と定義した。C `4fc174a622cb8dd9289cf3d7ea59eb5d7f1cd3367cb8922995d0d26ceb805657`、Python `66c7978695ac300d533a4e419c6949484c076e1fba868c3a43dd96d0392ee217`、JavaScript `6acceacabf8a90c13a544957208fa762751f58d0d340e7d2b436e4f3555bae6c` が新manifestと現行ソースで一致した。単独のCRや内容変更は同一視しない。
* `tools/source_hash.ps1` を追加し、`tools/generate_function_call_analysis.ps1` とCランナーで共用した。Python・JavaScriptランナー、Python・JavaScript・Cの照合テスト、READMEも同じ定義へ変更した。生成スクリプトは解析前後の正規化ソースハッシュが同じことを確認する。ハッシュのみの手修正はせず、Windows PowerShell 5.1でGCCレポート・アセンブリ、Pythonバイトコード、V8トレース、manifestを再生成した (`analysis_id=function-call-analysis-20260924-pr9-canonical`)。C資料は内容差分なし。各言語のfindingsを実資料から再抽出して照合した。
* `.gitattributes` は新規チェックアウトのLF化に引き続き使用する。既存ツリーの修正手順に強制チェックアウト、hard reset、cleanは含めない。処理系・版・アーキテクチャ・オプションの比較は維持し、内容変更や条件差は従来どおり `mismatched` となる。

### 実測した確認

* mainから新PRコミットへの通常更新: Cは `i/lf w/crlf attr/text eol=lf` のまま、Cの正規化SHA-256とmanifestは一致。PythonとJavaScriptはLFで、3言語のmanifest照合テスト、C解析テスト16件、JavaScript解析テスト22件が成功した。さらに一時複製のPython・JavaScriptをCRLFへ変換し、C 191件・Python 233件・JavaScript 22件のCRLF状態で、Python全体24件、JavaScript22件、C16件が成功した。正規化SHA-256は3言語ともmanifestと一致し、生バイトSHA-256はすべて異なった。
* この3言語CRLF状態で統合実行が成功し、`results/history/20260924_042004_function_call_numeric_sum/0022fb3141af4b44b1d1f36431352583/` を保存した。定義原本と保存定義はバイト一致、定義1件と結果3件のSHA-256は読み戻し再計算値と一致し、保存結果は `validated=3`、3言語のprovenanceは `matched` だった。
* 新規チェックアウトでは3ソースともLFで、Python全体24件、JavaScript22件、C16件、統合実行が成功した。保存先 `results/history/20260924_042054_function_call_numeric_sum/9aaeb9f0b5bd4e348ad08d0fd8cdf9f6/` についても定義原本のバイト一致、4件のSHA-256、`validated=3`、3言語の `matched` を再確認した。PR作業ツリーでも同じテスト群と統合実行が成功した。
* 一時複製のCソースへコメントを追記して照合すると `status=mismatched`、`mismatches=[source_sha256]`、インライン化 `not_checked` となり、元のバイト列へ復元した。Python・JavaScript・Cの単体テストでもCRLFだけの同値と内容変更の不一致を確認した。

### 未確認事項

* 他のOS、処理系・版、CPUアーキテクチャでの再生成と統合実行は未実施。異なる実行条件では解析結論を流用せず、不一致として扱う。

## 2026-09-24 保存済み履歴2件の比較条件判定

### 変更理由と判定基準

* PR #9の `archive.json` が指す `experiment.json` とC・JavaScript・Pythonの結果を読み、4件の記録SHA-256を各ファイルの生バイトで再計算する読み取り専用コマンド `tools/compare_archives.py` を追加した。固定ファイル名以外の参照、重複、欠落、壊れたJSON、ハッシュ不一致、既存Validatorの失敗、履歴内定義との不一致は終了コード2の検証エラーにする。
* 両履歴が整合してから定義のbenchmark・schema_version・config・expected_checksumを比較する。差があれば `incomparable` と項目別理由を出す。実験ID・実行ID・保存ID・保存日時や定義JSONの空白・キー順は条件差に使わない。
* 条件が一致した場合は同じ言語同士でOS・OS版・CPU名・アーキテクチャ・処理系と版を確認し、Cコンパイラと版、保存結果の解析用current条件にあるオプション・ソースSHA-256も照合する。差または欠落は `caution`、すべて記録済みで一致した場合は `comparable`。Cのコンパイルコマンドには毎回異なる一時パスが含まれるため、その文字列は比較しない。処理系が言語ごとに違うことは理由にしない。
* JSONは `schema_version: "1.0"`、`verdict`、理由の安定コード・フィールド・説明、入力パスを返す。破損時は `error` だけを返す。これは記録項目の一致判定で、同じCPU名による同一マシンの証明、速度ランキング、統計的有意差、最適化の因果関係は含まない。

### 実測した確認

* 新規テスト8件で同条件、定義JSONの整形・キー順差、ハッシュを正しく更新したconfig/schema差、環境差、情報不足、ソース差、コンパイルオプション差、保存結果改変、欠落、重複、不正参照、壊れたJSON、Validator失敗、定義との不一致、CLIのエラー終了を確認した。
* `python -B -m unittest discover -s tests -v`: 32件成功。`node --test tests/test_javascript_optimization_analysis.js`: 22件成功。`pwsh -NoProfile -File tests/test_c_optimization_analysis.ps1`: 16件成功。
* Windowsの隔離作業ツリーで `pwsh -NoProfile -File benchmarks/function_call_numeric_sum/run_all.ps1` を2回実行し、各回 `validated=3` と履歴保存が成功した。保存先は `20260924_080825_function_call_numeric_sum/76e604b6b6a44dc7bd2d91fd56967774` と `20260924_080901_function_call_numeric_sum/9aed0ca1e08c4361a48d29c3735e661b`。新コマンドでこの2件を検証・比較すると終了コード0、`caution`、理由は `INFORMATION_MISSING` / `environment.os_version` / `c` の1件だった。Cの実結果ではOS版がnullなので、他が一致しても注意付きとなる。
* 通常のWindowsサンドボックスではPythonが作成した一時ディレクトリへの書き込みと統合ランナーが作成した履歴の読み取りを拒否したため、該当テストと統合確認は承認付き実行経路で完了した。最初のサンドボックス失敗をテスト成功には算入していない。

### 未確認事項

* 他のOS、CPU、コンパイラ・処理系版での実機統合は未実施。履歴にはマシン固有ID、実行時負荷、ソース原本がないため、それらの同一性や性能差の理由は判定できない。

## 2026-09-24 PR #11 不正型の履歴検証とPython CI

### 再現と修正理由

* ハッシュを更新した保存履歴で結果の `config` を配列・nullに変えた場合、現行の `validate_function_call` は辞書型ガードにより既に検証エラーを返した。一方、benchmark・language・status・解析provenance等の配列では、Validatorの集合照合が `TypeError` を起こした。比較コマンドはその一部を `RESULT_VALIDATION_FAILED` に変換していたが、Validator自身の型誤りを隠していた。
* Validatorが文字列型を確認してから許可値集合と照合するようにした。解析の対象一覧・findings・最適化結果でも配列などを先に拒否し、比較で使用するengine・execution・environmentのコンテナ型を検査する。`tools/compare_archives.py` の `KeyError`・`TypeError`・`ValueError` 捕捉を外し、内部バグを検証エラーとして隠さない。
* 新しい回帰テストは `archive_results` で本物の履歴を作り、結果JSONの型変更後に `archive.json` のSHA-256を更新する。各例でValidatorがエラーを返し、`--json` の標準出力が解析可能な `error.code=RESULT_VALIDATION_FAILED`、終了コード2、`verdict` とスタックトレースなしであることを確認する。
* リポジトリに既存の `.github/workflows` はなかった。公式の安定版を確認し、Python 3.14と `actions/checkout@v7`・`actions/setup-python@v7` を使用するUbuntuジョブを追加した。`pull_request` とmainへのpushで `python -B -m unittest discover -s tests -q` だけを実行する。

### ローカル実測

* 修正前の新規テストでは、直接Validatorを呼ぶとbenchmark・language・status・provenance status・provenance applies_to・最適化結果の6種で `TypeError` を再現した。configの配列・nullは再現しなかった。
* 修正後、ハッシュ更新済み履歴の不正型・範囲14種を検査する新規テストが成功。過大整数で `math.isfinite` が起こす `OverflowError` も数値検証エラーとして扱う。`python -B -m unittest discover -s tests -q` は33件成功、`node --test tests/test_javascript_optimization_analysis.js` は22件成功、`pwsh -NoProfile -File tests/test_c_optimization_analysis.ps1` は16件成功。`git diff --check` も成功。

### CIと未確認事項

* コミット `a3b225e` のpull_request CIは [Python tests run 35933969426](https://github.com/tetsujisugimori-coder/LangBench-Live/actions/runs/35933969426) で成功した。Ubuntu 24.04.5、CPython 3.14.7、`python -B -m unittest discover -s tests -q` の実行ログに `Ran 33 tests` と `OK` を確認した。Ubuntu以外のOSでのPython CI、実機ベンチマークとWindows C統合はこのCIの対象外。

## 2026-09-24 保存済み履歴の測定値比較表示

### 設計判断と変更

* `tools/show_archive_metrics.py` を読み取り専用CLIとして追加した。既存の `compare_archives.load_archive` に履歴・生バイトSHA-256・Validator・定義照合を任せ、`compare_archives.compare_archives` の判定と理由をそのまま使用する。検証を別実装しない。元の `compare_archives.py --json` の形は変更しない。
* 3言語それぞれの `direct` と `function_call` について、保存済みの `median_ms` を同じ言語・ケース同士で対応させる。差は右−左、変化率は差÷左×100。計算中は丸めず、テキスト表示時だけ12桁の有効数字にする。JSONは丸めていないPython数値を出す。`faster` は保存中央値だけの方向を表す。
* `comparable` は6ケースの中央値・差・変化率・方向を表示する。`caution` は同じ値に参考値の注意を付け、既存の理由コード・フィールド・説明を残す。`incomparable` は理由と単独中央値のみを表示し、差・変化率・方向のキーをJSONからも省く。検証失敗は元のコマンドと同じ終了コード2・JSONの `error` 構造にする。
* 左中央値0の変化率は `null` と `LEFT_MEDIAN_ZERO`、負の左中央値は `LEFT_MEDIAN_NEGATIVE` とする。有限値を得られない差・変化率も `null` と `NONFINITE_RESULT` にし、JSON出力の `NaN`・`Infinity` を禁止する。既存Validatorは保存中央値をサンプル由来の中央値と相対 `1e-9`・絶対 `0.001` msの許容誤差で照合するので、完全一致は保証しないことをREADMEに記載した。
* READMEに実行例、JSONのキーと単位、3判定の表示、計算式、CのOS版未記録による注意理由、解釈上の限界を追記した。統計的有意差、最適化の因果関係、言語間ランキング、UI、Memo-Nexus連携は実装しない。

### ローカル実測

* 新規8テストで3判定、数値の正負、CのOS版欠損理由、改変・再ハッシュ済みの不正中央値、0除算、Validator許容範囲内の保存中央値、テキストとJSONを確認した。`python -B -m unittest discover -s tests -q`: **41件成功**。既存33件も含む。隔離作業ツリーのWindows通常サンドボックスでは一時履歴への書き込みを拒否されたため、その失敗は成功に含めず、承認付き実行経路で再実行した。
* 実測履歴はこのチェックアウトに保存されていない（`results/history/` はGit管理外）。回帰テストは `archive_results` で実際の履歴形式を生成して検証した。実機での新しいベンチマーク測定や他OSでの実行は行っていない。

### PR #13 CI

* [Python tests run 35936977745](https://github.com/tetsujisugimori-coder/LangBench-Live/actions/runs/35936977745) はpull requestのコミット `cf374c0` に対して成功した。UbuntuのPython 3.14.7で `python -B -m unittest discover -s tests -q` が実行され、ログの `Ran 41 tests in 2.086s` と `OK` を確認した。CIはPythonテストのみで、Windowsや実測ベンチマークの実行は含まない。

## 2026-09-24 PR #13 サンプル由来中央値への修正

### 原因と修正

* 既存Validatorは `samples_ms` を昇順に並べ、偶数件の中央2値を平均して中央値を計算し、保存 `median_ms` を `math.isclose`（相対許容誤差 `1e-9`、絶対許容誤差 `0.001` ms）で受け入れる。修正前のCLIは保存 `median_ms` を表示・差・変化率・`faster` に使っていた。両履歴のサンプルが `[1.0, 2.0]` でも右の保存中央値だけ1.5005 msにした有効な履歴で、左1.5 ms、右1.5005 ms、差約+0.0005 ms、変化率約+0.033333%、`faster: "left"` と誤表示することを修正前のテストで再現した。
* 中央値の計算を `validate_result_json.median_from_samples` にまとめ、ValidatorとCLIで共用した。CLIは検証済みサンプルから再計算した中央値だけを表示・差・変化率・方向に使う。保存 `median_ms` のValidator照合は維持し、履歴JSONは更新しない。上記の同一サンプル例では両方1.5 ms、差0 ms、変化率0%、`faster: "equal"` となる。
* `equal` は再計算した中央値の一致のみを表し、サンプル分布全体の一致を示さない。READMEの計算根拠、JSONフィールドの意味、同一サンプル例を修正した。`comparable` / `caution` / `incomparable`、CのOS版欠損理由、0除算、破損履歴の扱いは維持した。

### ローカル実測

* 修正前の新しい期待値では対象テストが失敗し、実際のJSONは `(left_median_ms, right_median_ms, delta_ms, change_percent, faster) = (1.5, 1.5005, 0.0004999999999999449, 0.03333333333332966, "left")` だった。修正後は同一サンプルで `(1.5, 1.5, 0.0, 0.0, "equal")` とテキストの `同じ中央値` を確認した。異なるサンプル分布でも中央値が一致するテストを追加し、正負の差・方向を検証する既存テストも維持した。
* `python -B -m unittest tests.test_show_archive_metrics tests.test_compare_archives -q`: **18件成功**。`python -B -m unittest discover -s tests -q`: **42件成功**。関連テストの最初の実行はWindowsの一時履歴フォルダ削除で `WinError 145` が1件発生したが、残った `history` は空で、同じ18件と全42件の再実行では再発しなかった。比較のアサーション失敗ではない。この一過性エラーは成功件数に含めていない。

## 2026-09-24 独立5実行の履歴中央値の揺れ

### 設計判断

* `tools/show_archive_variability.py` は異なる履歴フォルダ2件以上を入力順に読み、既存の `load_archive` にSHA-256・Validator・実験定義の照合を、`compare_archives` に全組の条件判定を任せる。各実行の6中央値はPR #13で共用化した `median_from_samples` から求める。履歴の同一フォルダ重複指定は独立した2実行ではないため `DUPLICATE_ARCHIVE` とする。
* 全組 `comparable` の場合は6ケースの最小・最大・差を表示する。`caution` があれば同じ数値を `reference` とし、各組の原因コードと対象フィールドを残す。1組でも `incomparable` があれば集団の集計値をJSONからも省く。JSONは単位、全体判定、各履歴、全組判定、表示可能な集計値を分け、非有限の差は `null` と理由を返す。テキストはWindowsの既定出力文字コードでも表示できる区切り文字を使う。既存2履歴CLIの仕様は変更しない。
* 1履歴内の50サンプルから得た中央値を1実行の代表値とし、独立5実行の中央値の範囲を記述する。統計的有意差、最適化の効果、言語全体の順位は判定しない。

### 実行コマンドと結果

* PR #13のマージ済みmain `e807bf9` とGitHub側mainの同一SHAを確認し、新ブランチ `codex/repeated-archive-variability` を作成した。作業ツリーの無関係な未追跡ファイルは保持した。
* `python -B -m unittest tests.test_show_archive_variability tests.test_show_archive_metrics tests.test_compare_archives -q`: **33件成功**。Windowsの既定文字コードを模したcp932出力テスト追加後、`python -B -m unittest discover -s tests -q`: **58件成功**。最初の通常サンドボックス実行は一時履歴フォルダへの書き込み拒否で失敗し、権限を付けた再実行で成功した。新規7テストは同条件、注意、比較不可、改変、入力順、重複、Windows文字コードを検査する。
* 元の最新結果を変えずに実測するため、コミット `00fec88` から `C:\Users\tetsu\Documents\Codex\langbench-variability-measure` に隔離worktreeを作った。3言語の測定ソースはすべて作業ツリーでLF。そこで `1..5 | ForEach-Object { pwsh -NoProfile -File benchmarks/function_call_numeric_sum/run_all.ps1 }` を逐次実行し、5回とも `validated=3`、`status=success`、履歴保存を確認した。履歴パスは次のとおり。
  1. `results/history/20260924_094547_function_call_numeric_sum/8b862ce58b6d4a799b785b5a8be5ec2f`
  2. `results/history/20260924_094553_function_call_numeric_sum/8e133dec9dca4214b6f68807c1dac57f`
  3. `results/history/20260924_094559_function_call_numeric_sum/5866fe81f4764e69ac19e74675b06524`
  4. `results/history/20260924_094605_function_call_numeric_sum/670191b0f9dc475b873df6920c6fd286`
  5. `results/history/20260924_094611_function_call_numeric_sum/0099f426273a48b59256b23e47830b25`
* 上記5パスを `python tools/show_archive_variability.py @archives` と `python tools/show_archive_variability.py --json @archives` で読み、10組は `comparable=0`、`caution=10`、`incomparable=0`。各組の理由は `INFORMATION_MISSING`、`environment.os_version`、言語 `c` の1件だった。以下はすべて**参考値**で、単位はms。各セルは5実行の中央値の最小・最大・差（最大−最小）。

| 言語 / ケース | 実行1 | 実行2 | 実行3 | 実行4 | 実行5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| C / direct | 0.114 | 0.113 | 0.105 | 0.115 | 0.104 |
| C / function_call | 0.414 | 0.418 | 0.410 | 0.418 | 0.418 |
| JavaScript / direct | 0.4985 | 0.4865 | 0.4615 | 0.4965 | 0.4935 |
| JavaScript / function_call | 0.522 | 0.512 | 0.444 | 0.4475 | 0.497 |
| Python / direct | 18.545 | 19.315 | 19.8115 | 18.9285 | 18.9845 |
| Python / function_call | 32.188 | 32.845 | 32.2415 | 32.130 | 32.615 |

| 言語 / ケース | 最小 | 最大 | 差 |
| --- | ---: | ---: | ---: |
| C / direct | 0.104 | 0.115 | 0.011 |
| C / function_call | 0.410 | 0.418 | 0.008 |
| JavaScript / direct | 0.4615 | 0.4985 | 0.037 |
| JavaScript / function_call | 0.444 | 0.522 | 0.078 |
| Python / direct | 18.545 | 19.8115 | 1.2665 |
| Python / function_call | 32.130 | 32.845 | 0.715 |

### 制限

* この実測はこのWindows環境の5回だけで、CのOS版は保存結果に記録されていない。負荷・電源状態など未記録の要因も同一とは確認できない。6ケースの範囲は記述的な値であり、統計的有意差や因果関係、他環境や言語全体への一般化を示さない。
* 実測した履歴と集計JSONは隔離worktreeにありGit管理外。回帰テストの生成履歴を実機測定として数えていない。CIはPythonテストのみで、Windows統合ベンチマークは対象外。
