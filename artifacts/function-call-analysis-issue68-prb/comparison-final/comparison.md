# Issue #68 PR-B: Windows 実機解析と PR #67 の条件照合

- analysis ID: `issue68-pra-69-36797708544`
- analysis code SHA: `98dbb01d36c204f352d5b4690de72b570fdb075e`
- measurement series: `issue66-balanced-final-01`
- measurement Git SHA: `fde3f78b385034248bac9dfe7a97c8da37ffb3ae`
- measurement manifest SHA-256: `60a5b14eeb8f287910b248e832a177264593682eda3952f06219e4a13a49c4a4`
- trace flags: `["--trace-opt", "--trace-deopt", "--trace-turbo-inlining"]`

| language | source | runtime | implementation | architecture | options | both orders | exact |
|---|---:|---:|---:|---:|---:|---:|---:|
| c | yes | yes | yes | yes | yes | yes | yes |
| python | yes | yes | yes | yes | no | yes | no |
| javascript | no | yes | no | yes | yes | yes | no |

## 言語別条件と所見

### c

- source SHA-256: measurement `b107c19cdcc972e23c5968cc217f7c9ec88b06b840ab5aac8daa888fbe16cad3`; analysis `b107c19cdcc972e23c5968cc217f7c9ec88b06b840ab5aac8daa888fbe16cad3`
- analysis condition SHA-256 (canonical sorted JSON): `7d5579bf83f485d13d78a899c8b1b30dde423c45a09216c0301a5519cb46881d`
- runtime: measurement `{'name': 'GCC', 'version': 'gcc.exe (Rev5, Built by MSYS2 project) 16.1.0'}`; analysis `{'name': 'GCC', 'version': 'gcc (Rev5, Built by MSYS2 project) 16.1.0'}`
- implementation: measurement `{'name': 'GCC', 'version': 'gcc.exe (Rev5, Built by MSYS2 project) 16.1.0'}`; analysis `{'name': 'GCC', 'version': 'gcc (Rev5, Built by MSYS2 project) 16.1.0'}`
- architecture: measurement `X64`; analysis `x64`
- options: measurement `['-O2', '-std=c11', '-Wall', '-Wextra']`; analysis `['-O2', '-std=c11', '-Wall', '-Wextra']`
- measurement order: `['direct_first', 'function_call_first', 'function_call_first', 'direct_first', 'direct_first', 'function_call_first', 'function_call_first', 'direct_first', 'direct_first', 'function_call_first', 'function_call_first', 'direct_first']`
- analysis order coverage: `{'basis': 'static_analysis', 'confirmed': ['direct_first', 'function_call_first'], 'unconfirmed': []}`
- findings: `{'inlining': {'result': 'not_detected'}, 'vectorization': {'result': 'detected'}, 'simd': {'result': 'detected', 'isa': ['SSE2']}}`
- evidence: `[{'type': 'assembly', 'path': 'artifacts/function-call-analysis/main.s'}, {'type': 'compiler_report', 'path': 'artifacts/function-call-analysis/gcc-optimization.txt'}]`
- evidence SHA-256: `{'main.s': '3c7b91c62b342947251eb6f8f5a203f7e716ec24c6b58087088b3329ff316aca', 'gcc-optimization.txt': 'e1293028ed09ec5eec62db1340518a47cd0eda57237f5226a844227067f31b76'}`
- applicability reasons: `[]`
- source mismatch impact: `not_assessed`

### python

- source SHA-256: measurement `f174bd2a03c028a333aa26550185fb2aa9636fe1b48235d68e14e6ef6252adcc`; analysis `f174bd2a03c028a333aa26550185fb2aa9636fe1b48235d68e14e6ef6252adcc`
- analysis condition SHA-256 (canonical sorted JSON): `5ad1456f26f84c499796a3b9a3820bc1eb4f27d16da8301194b601721eeaa378`
- runtime: measurement `{'name': 'CPython', 'version': 'Python 3.14.7'}`; analysis `{'name': 'CPython', 'version': '3.14.7'}`
- implementation: measurement `{'name': 'CPython', 'version': 'Python 3.14.7'}`; analysis `{'name': 'CPython', 'version': '3.14.7'}`
- architecture: measurement `X64`; analysis `amd64`
- options: measurement `[]`; analysis `['optimize=0']`
- measurement order: `['direct_first', 'function_call_first', 'function_call_first', 'direct_first', 'direct_first', 'function_call_first', 'function_call_first', 'direct_first', 'direct_first', 'function_call_first', 'function_call_first', 'direct_first']`
- analysis order coverage: `{'basis': 'static_analysis', 'confirmed': ['direct_first', 'function_call_first'], 'unconfirmed': []}`
- findings: `{'inlining': {'result': 'not_detected'}, 'vectorization': {'result': 'not_detected'}, 'simd': {'result': 'not_checked', 'isa': []}}`
- evidence: `[{'type': 'disassembly', 'path': 'artifacts/function-call-analysis/python-bytecode.txt'}]`
- evidence SHA-256: `{'python-bytecode.txt': 'eb38a209049a8843ff52f466604ed2e3d9ff233d5d649964d4591efd52353ce9'}`
- applicability reasons: `['options']`
- source mismatch impact: `not_assessed`

### javascript

- source SHA-256: measurement `0838635d22bd28ee110915d7f3a0db0b3bb7d6c211985f4b13ed32800e6c5169`; analysis `6fe69643f08742fc7aaf51ba0b65a9312add16f5ed9ae9eacf3d2426c1d91473`
- analysis condition SHA-256 (canonical sorted JSON): `4e4653dd11cca3712f93d35cc174b8932782bb3ad96414db206476ba1b9f118f`
- runtime: measurement `{'name': 'Node.js', 'version': 'v24.20.0'}`; analysis `{'name': 'Node.js', 'version': 'v24.20.0'}`
- implementation: measurement `None`; analysis `{'name': 'V8', 'version': '13.6.233.17-node.53'}`
- architecture: measurement `X64`; analysis `x64`
- options: measurement `[]`; analysis `[]`
- measurement order: `['direct_first', 'function_call_first', 'function_call_first', 'direct_first', 'direct_first', 'function_call_first', 'function_call_first', 'direct_first', 'direct_first', 'function_call_first', 'function_call_first', 'direct_first']`
- analysis order coverage: `{'basis': 'trace_observed', 'confirmed': ['direct_first', 'function_call_first'], 'unconfirmed': []}`
- findings: `{'jit': {'result': 'detected'}, 'inlining': {'result': 'detected'}, 'vectorization': {'result': 'not_checked'}, 'simd': {'result': 'not_checked', 'isa': []}}`
- evidence: `[{'type': 'jit_trace', 'path': 'artifacts/function-call-analysis/v8-optimization-direct_first.txt'}, {'type': 'jit_trace', 'path': 'artifacts/function-call-analysis/v8-optimization-function_call_first.txt'}, {'type': 'order_findings', 'path': 'artifacts/function-call-analysis/javascript-order-findings.json'}]`
- evidence SHA-256: `{'v8-optimization-direct_first.txt': '923cac58cfef8fd47f52e95b59b994deba21517136e9ea43f9355333dbe24179', 'v8-optimization-function_call_first.txt': 'c3dccb5c453c5733e1f2a45506f868d9becbfa5d40cc3e83fa1984a9a1afe27d', 'javascript-order-findings.json': '1ba44510a4507b7f270e115428218b53ea1709985706281cb7c982df1c3eac11'}`
- applicability reasons: `['source', 'implementation']`
- source mismatch impact: `unknown`

Python の解析条件 `optimize=0` と測定 manifest の空 options は、正規化の根拠が公開資料にないため不一致として扱う。

PR #67 の測定 manifest には V8 implementation/version が独立した値としてない。Node.js version 一致から V8 一致を推定しない。

JavaScript の trace は性能本測定ではない。条件と観測結果の並置は、最適化が性能差を生じさせたという因果関係を示さない。source が一致しない場合の影響は unknown とする。
