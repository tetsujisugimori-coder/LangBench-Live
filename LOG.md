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
