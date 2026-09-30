param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')][string]$AnalysisId,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [Parameter(Mandatory = $true)][string]$SharedRepositoryPath,
    [string]$ExpectedSha,
    [string]$GccExecutable = 'gcc',
    [string[]]$AllowedRemote = @('https://github.com/tetsujisugimori-coder/LangBench-Live.git','https://github.com/tetsujisugimori-coder/LangBench-Live','git@github.com:tetsujisugimori-coder/LangBench-Live.git'),
    [ValidateSet("direct_first", "function_call_first")][string]$TestFailTraceOrder
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -lt 7 -or
    ($PSVersionTable.PSVersion.Major -eq 7 -and $PSVersionTable.PSVersion.Minor -lt 2) -or
    [Environment]::Version.Major -lt 6) {
    throw 'analysis generation requires PowerShell 7.2 or later on .NET 6 or later'
}

function ConvertTo-ProcessArgument {
    param([string]$Value)
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    $escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function Invoke-CapturedProcess {
    param([string]$FileName, [string[]]$Arguments, [string]$WorkingDirectory)
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $FileName
    $info.WorkingDirectory = $WorkingDirectory
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    if ($null -ne $info.ArgumentList) {
        foreach ($argument in $Arguments) { $info.ArgumentList.Add($argument) }
    } else {
        $info.Arguments = (($Arguments | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join " ")
    }
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $info
    if (-not $process.Start()) { throw "failed to start $FileName" }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    return [ordered]@{ stdout = $stdout; stderr = $stderr; exit_code = $process.ExitCode }
}

function Get-TextHash([string]$Value) {
    $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
}

function Protect-ArtifactText([string]$Value) {
    $safe = $Value
    foreach ($pair in @(@($artifactDir, '<analysis-package>'), @($projectRoot, '<checkout>'), @($sharedRoot, '<shared-repository>'))) {
        if ($pair[0]) { $safe = [regex]::Replace($safe, [regex]::Escape([string]$pair[0]), [string]$pair[1], 'IgnoreCase') }
    }
    $safe = [regex]::Replace($safe, '(?i)(gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,}|Bearer\s+\S+|(?:token|password|secret|authorization)\s*[:=]\s*\S+)', '<redacted>')
    $safe = [regex]::Replace($safe, '(?i)(?<![A-Za-z0-9_])(?:[A-Z]:\\|/(?:home|Users|tmp|var)/)[^\s"''<>]+', '<absolute-path>')
    return $safe
}

function Write-RunState {
    $path = Join-Path $artifactDir 'run-state.json'
    $temporary = "$path.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        [IO.File]::WriteAllText($temporary, (($script:runState | ConvertTo-Json -Depth 12) + "`n"), [Text.UTF8Encoding]::new($false))
        [IO.File]::Move($temporary, $path, $true)
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Invoke-RecordedStage {
    param([string]$Name, [string]$FileName, [string[]]$Arguments,
          [string]$SourceLanguage, [string[]]$EvidencePaths = @(), [switch]$AllowFailure)
    $safeCommand = @($FileName) + @($Arguments | ForEach-Object { Protect-ArtifactText $_ })
    $entry = [ordered]@{
        status = 'running'; command = $safeCommand; exit_code = $null
        stdout_log = "stage-logs/$Name.stdout.txt"; stderr_log = "stage-logs/$Name.stderr.txt"
        source_sha256 = if ($SourceLanguage) { $sourceHashes[$SourceLanguage] } else { $null }
        condition_sha256 = Get-TextHash (($safeCommand | ConvertTo-Json -Compress) + "|" + $SourceLanguage)
        evidence_sha256 = [ordered]@{}
    }
    $script:runState.stages[$Name] = $entry
    Write-RunState
    try {
        $result = Invoke-CapturedProcess $FileName $Arguments $projectRoot
        Write-Utf8 (Join-Path $artifactDir $entry.stdout_log) (Protect-ArtifactText $result.stdout)
        Write-Utf8 (Join-Path $artifactDir $entry.stderr_log) (Protect-ArtifactText $result.stderr)
        $entry.exit_code = $result.exit_code
        foreach ($log in @($entry.stdout_log, $entry.stderr_log)) {
            $entry.evidence_sha256[$log] = (Get-FileHash -LiteralPath (Join-Path $artifactDir $log) -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        foreach ($path in $EvidencePaths) {
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                $entry.evidence_sha256[(Split-Path -Leaf $path)] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }
        $entry.status = if ($result.exit_code -eq 0) { 'success' } else { 'failed' }
        Write-RunState
        if ($result.exit_code -ne 0 -and -not $AllowFailure) { throw "$Name failed with exit code $($result.exit_code)" }
        return $result
    } catch {
        if ($entry.status -eq 'running') {
            $entry.status = 'failed'
            Write-Utf8 (Join-Path $artifactDir $entry.stderr_log) (Protect-ArtifactText $_.Exception.Message)
            Write-RunState
        }
        throw
    }
}

function Add-StageEvidence([string]$Name, [string]$Path) {
    $script:runState.stages[$Name].evidence_sha256[(Split-Path -Leaf $Path)] = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-RunState
}

function Write-Utf8 {
    param([string]$Path, [string]$Content)
    $temporaryPath = Join-Path (Split-Path -Parent $Path) ((Split-Path -Leaf $Path) + "." + [guid]::NewGuid().ToString("N") + ".tmp")
    try {
        [System.IO.File]::WriteAllText($temporaryPath, $Content.Replace("`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
        Move-Item -LiteralPath $temporaryPath -Destination $Path
    } finally {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    }
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$operationLock = $null
$measurementLock = $null
try {
$sharedRoot = [IO.Path]::GetFullPath($SharedRepositoryPath).TrimEnd('\', '/')
if (-not (Test-Path -LiteralPath $sharedRoot -PathType Container)) { throw "shared repository does not exist" }
$sharedTop = (& git -C $sharedRoot rev-parse --show-toplevel).Trim()
$gitDirectory = (& git -C $sharedRoot rev-parse --path-format=absolute --git-common-dir).Trim()
if ($LASTEXITCODE -ne 0 -or [IO.Path]::GetFullPath($sharedTop).TrimEnd('\', '/') -ine $sharedRoot) { throw "shared repository root is invalid" }
try {
    $operationLock = [IO.File]::Open((Join-Path $gitDirectory "langbench-operation.lock"), 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    throw "another synchronization, measurement, or analysis operation is active"
}
if ($AllowedRemote -inotcontains ((& git -C $sharedRoot remote get-url origin).Trim())) { throw "shared repository origin is not trusted" }
$codeHead = (& git -C $projectRoot rev-parse HEAD).Trim()
$sharedHead = (& git -C $sharedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sharedHead -ne $codeHead) { throw "shared repository is not synchronized to the analyzed SHA" }
$branchOutput = @(& git -C $sharedRoot symbolic-ref --quiet --short HEAD)
$branchExitCode = $LASTEXITCODE
if ($branchExitCode -ne 0 -or $branchOutput.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$branchOutput[0])) {
    throw "shared repository is detached; main is required"
}
if ([string]$branchOutput[0] -ne "main") { throw "shared repository branch is not main: $($branchOutput[0])" }
if (@(& git -C $sharedRoot status --porcelain --untracked-files=no).Count) { throw "shared repository has tracked changes" }
try {
    $measurementLock = [IO.File]::Open((Join-Path $sharedRoot "results/function_call_numeric_sum.lock"), 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    throw "another function-call measurement or analysis operation is active"
}
. (Join-Path $projectRoot "tools\source_hash.ps1")
$artifactDir = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $artifactDir) { throw "analysis output already exists: $artifactDir" }
[System.IO.Directory]::CreateDirectory($artifactDir) | Out-Null
[System.IO.Directory]::CreateDirectory((Join-Path $artifactDir 'stage-logs')) | Out-Null
$script:runState = [ordered]@{
    schema_version = '1.0'; analysis_id = $AnalysisId; status = 'running'
    code_sha = $null; stages = [ordered]@{}; validation_json = 'validation.json'; error = $null
}
Write-RunState
Write-Utf8 (Join-Path $artifactDir 'validation.json') "{`"status`":`"pending`"}`n"
$cRelativeSource = "benchmarks/function_call_numeric_sum/c/main.c"
$pythonRelativeSource = "benchmarks/function_call_numeric_sum/python/main.py"
$javascriptRelativeSource = "benchmarks/function_call_numeric_sum/javascript/main.js"
$cSource = Join-Path $projectRoot "benchmarks\function_call_numeric_sum\c\main.c"
$pythonSource = Join-Path $projectRoot "benchmarks\function_call_numeric_sum\python\main.py"
$javascriptSource = Join-Path $projectRoot "benchmarks\function_call_numeric_sum\javascript\main.js"
$sources = [ordered]@{ c = $cSource; python = $pythonSource; javascript = $javascriptSource }
$sourceHashes = @{}
foreach ($language in $sources.Keys) {
    $sourceHashes[$language] = Get-CanonicalSourceHash -Path $sources[$language]
}
$gccReport = Join-Path $artifactDir "gcc-optimization.txt"
$assembly = Join-Path $artifactDir "main.s"
$pythonBytecode = Join-Path $artifactDir "python-bytecode.txt"
$v8TracePaths = [ordered]@{
    direct_first = Join-Path $artifactDir "v8-optimization-direct_first.txt"
    function_call_first = Join-Path $artifactDir "v8-optimization-function_call_first.txt"
}
$v8FindingsPath = Join-Path $artifactDir "javascript-order-findings.json"
$manifestPath = Join-Path $artifactDir "manifest.json"
$extractor = Join-Path $projectRoot "tools\extract_function_call_findings.py"
$analyzedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$gitSha = (& git -C $projectRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $gitSha -notmatch '^[0-9a-f]{40}$') { throw "failed to obtain the analyzed Git SHA" }
if ($ExpectedSha -and $gitSha -ne $ExpectedSha) { throw 'checkout SHA differs from trusted main SHA' }
$script:runState.code_sha = $gitSha
Write-RunState

$gccVersionOutput = Invoke-RecordedStage 'gcc-version' $GccExecutable @('--version') 'c'
$gccVersion = ($gccVersionOutput.stdout -split "`r?`n")[0]
if ([string]::IsNullOrWhiteSpace($gccVersion)) { throw "failed to obtain GCC version" }
$gccVersion = $gccVersion -replace '^gcc\.exe ', 'gcc '
$cOptions = @("-O2", "-std=c11", "-Wall", "-Wextra")
Remove-Item -LiteralPath $gccReport, $assembly -Force -ErrorAction SilentlyContinue
$gccArgs = @($cRelativeSource) + $cOptions + @("-S", "-masm=intel", "-fopt-info-all=$gccReport", "-o", $assembly)
Invoke-RecordedStage 'gcc' $GccExecutable $gccArgs 'c' @($gccReport, $assembly) | Out-Null
$gccReportContent = [System.IO.File]::ReadAllText($gccReport)
$gccReportContent = [regex]::Replace($gccReportContent, '(?m)[\t ]+(?=\r?$)', '')
Write-Utf8 $gccReport (Protect-ArtifactText $gccReportContent)
Write-Utf8 $assembly (Protect-ArtifactText ([IO.File]::ReadAllText($assembly)))
Add-StageEvidence 'gcc' $gccReport
Add-StageEvidence 'gcc' $assembly

$pythonInfo = (Invoke-RecordedStage 'python-version' 'python' @("-c", "import json,platform,sys; print(json.dumps({'name': platform.python_implementation(), 'version': platform.python_version(), 'architecture': platform.machine().lower(), 'optimize': sys.flags.optimize}))") 'python').stdout | ConvertFrom-Json
$pythonDis = Invoke-RecordedStage 'python-disassembly' 'python' @('-m', 'dis', $pythonRelativeSource) 'python'
if (-not [string]::IsNullOrWhiteSpace($pythonDis.stderr)) { throw "Python disassembly wrote to stderr: $($pythonDis.stderr)" }
Write-Utf8 $pythonBytecode (Protect-ArtifactText $pythonDis.stdout)
Add-StageEvidence 'python-disassembly' $pythonBytecode

$nodeInfo = (Invoke-RecordedStage 'node-version' 'node' @("-p", "JSON.stringify({node:process.version,v8:process.versions.v8,architecture:require('os').arch(),options:(process.env.NODE_OPTIONS||'').trim().split(/\s+/).filter(Boolean)})") 'javascript').stdout | ConvertFrom-Json
$nodeInfo.options = @($nodeInfo.options | ForEach-Object { Protect-ArtifactText $_ })
$javascriptOrderFindings = [ordered]@{}
foreach ($order in @("direct_first", "function_call_first")) {
    $traceArgs = if ($TestFailTraceOrder -eq $order) {
        @("-e", "console.log('partial stdout'); console.error('fixture failure'); process.exit(23)")
    } else {
        @("--trace-opt", "--trace-deopt", "--trace-turbo-inlining", "tools/trace_function_call_javascript.js", $order)
    }
    $nodeTrace = Invoke-RecordedStage "node-trace-$order" 'node' $traceArgs 'javascript' -AllowFailure
    $traceStdout = (($nodeTrace.stdout -split "`r?`n") | Where-Object { $_ }) -join "`n"
    $traceStderr = (($nodeTrace.stderr -split "`r?`n") | Where-Object { $_ }) -join "`n"
    $traceContent = "# order=$order`n# exit_code=$($nodeTrace.exit_code)`n# stdout`n$traceStdout`n# stderr`n$traceStderr`n"
    Write-Utf8 $v8TracePaths[$order] (Protect-ArtifactText $traceContent)
    Add-StageEvidence "node-trace-$order" $v8TracePaths[$order]
    if ($nodeTrace.exit_code -ne 0) { throw "Node trace failed for $order with exit code $($nodeTrace.exit_code)" }
    $javascriptOrderFindings[$order] = (Invoke-RecordedStage "javascript-extractor-$order" 'python' @($extractor, '--language', 'javascript', '--artifact', $v8TracePaths[$order]) 'javascript' @($v8TracePaths[$order])).stdout | ConvertFrom-Json
}
Write-Utf8 $v8FindingsPath (($javascriptOrderFindings | ConvertTo-Json -Depth 8) + "`n")

$architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
$cFindings = (Invoke-RecordedStage 'c-extractor' 'python' @($extractor, '--language', 'c', '--report', $gccReport, '--assembly', $assembly, '--architecture', $architecture) 'c' @($gccReport, $assembly)).stdout | ConvertFrom-Json
$pythonFindings = (Invoke-RecordedStage 'python-extractor' 'python' @($extractor, '--language', 'python', '--artifact', $pythonBytecode) 'python' @($pythonBytecode)).stdout | ConvertFrom-Json
$javascriptFindings = [ordered]@{}
foreach ($findingName in @("jit", "inlining", "vectorization", "simd")) {
    $directFinding = $javascriptOrderFindings.direct_first.$findingName
    $calledFinding = $javascriptOrderFindings.function_call_first.$findingName
    if (($directFinding | ConvertTo-Json -Compress) -eq ($calledFinding | ConvertTo-Json -Compress)) {
        $javascriptFindings[$findingName] = $directFinding
    } elseif ($findingName -eq "simd") {
        $javascriptFindings[$findingName] = [ordered]@{ result = "unknown"; isa = @() }
    } else {
        $javascriptFindings[$findingName] = [ordered]@{ result = "unknown" }
    }
}
foreach ($language in $sources.Keys) {
    if ((Get-CanonicalSourceHash -Path $sources[$language]) -ne $sourceHashes[$language]) {
        throw "source changed while generating $language analysis"
    }
}
$manifest = [ordered]@{
    schema_version = "1.0"
    analysis_id = $AnalysisId
    generated_at = $analyzedAt
    languages = [ordered]@{
        c = [ordered]@{
            artifact_id = "$AnalysisId-c"
            analyzed_at = $analyzedAt
            applies_to = @("inlining", "vectorization", "simd")
            condition = [ordered]@{
                source_sha256 = $sourceHashes.c
                implementation = [ordered]@{ name = "GCC"; version = $gccVersion }
                architecture = $architecture
                options = $cOptions
            }
            generation_commands = @(
                @("gcc", "benchmarks/function_call_numeric_sum/c/main.c") + $cOptions + @("-S", "-masm=intel", "-fopt-info-all=artifacts/function-call-analysis/gcc-optimization.txt", "-o", "artifacts/function-call-analysis/main.s")
            )
            findings = $cFindings
            evidence = @(
                [ordered]@{ type = "assembly"; path = "artifacts/function-call-analysis/main.s" },
                [ordered]@{ type = "compiler_report"; path = "artifacts/function-call-analysis/gcc-optimization.txt" }
            )
        }
        python = [ordered]@{
            artifact_id = "$AnalysisId-python"
            analyzed_at = $analyzedAt
            applies_to = @("inlining", "vectorization", "simd")
            condition = [ordered]@{
                source_sha256 = $sourceHashes.python
                implementation = [ordered]@{ name = $pythonInfo.name; version = $pythonInfo.version }
                architecture = $pythonInfo.architecture
                options = @("optimize=$($pythonInfo.optimize)")
            }
            generation_commands = @(@("python", "-m", "dis", "benchmarks/function_call_numeric_sum/python/main.py"))
            findings = $pythonFindings
            evidence = @([ordered]@{ type = "disassembly"; path = "artifacts/function-call-analysis/python-bytecode.txt" })
        }
        javascript = [ordered]@{
            artifact_id = "$AnalysisId-javascript"
            analyzed_at = $analyzedAt
            applies_to = @("jit", "inlining", "vectorization", "simd")
            condition = [ordered]@{
                source_sha256 = $sourceHashes.javascript
                implementation = [ordered]@{ name = "V8"; version = $nodeInfo.v8 }
                architecture = $nodeInfo.architecture
                options = @($nodeInfo.options)
            }
            generation_commands = @(@("node", "--trace-opt", "--trace-deopt", "--trace-turbo-inlining", "tools/trace_function_call_javascript.js", "<measurement-order>"))
            findings = $javascriptFindings
            runtime = [ordered]@{ name = "Node.js"; version = $nodeInfo.node }
            evidence = @(
                [ordered]@{ type = "jit_trace"; path = "artifacts/function-call-analysis/v8-optimization-direct_first.txt" },
                [ordered]@{ type = "jit_trace"; path = "artifacts/function-call-analysis/v8-optimization-function_call_first.txt" },
                [ordered]@{ type = "order_findings"; path = "artifacts/function-call-analysis/javascript-order-findings.json" }
            )
        }
    }
}
Write-Utf8 $manifestPath (($manifest | ConvertTo-Json -Depth 12) + "`n")
$evidenceHashes = [ordered]@{}
foreach ($path in @($gccReport, $assembly, $pythonBytecode, $v8TracePaths.direct_first, $v8TracePaths.function_call_first, $v8FindingsPath, $manifestPath)) {
    $evidenceHashes[(Split-Path -Leaf $path)] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
$provenance = [ordered]@{
    schema_version = "1.0"
    analysis_id = $AnalysisId
    code_sha = $gitSha
    generated_at = $analyzedAt
    operating_system = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
    architecture = $architecture
    trace_options = @("--trace-opt", "--trace-deopt", "--trace-turbo-inlining")
    order_coverage = [ordered]@{
        c = [ordered]@{ basis = "static_analysis"; confirmed = @("direct_first", "function_call_first"); unconfirmed = @() }
        python = [ordered]@{ basis = "static_analysis"; confirmed = @("direct_first", "function_call_first"); unconfirmed = @() }
        javascript = [ordered]@{ basis = "trace_observed"; confirmed = @("direct_first", "function_call_first"); unconfirmed = @() }
    }
    javascript_orders = [ordered]@{
        direct_first = [ordered]@{
            command = @("node", "--trace-opt", "--trace-deopt", "--trace-turbo-inlining", "tools/trace_function_call_javascript.js", "direct_first")
            stimulus = [ordered]@{ iterations = 100; item_count = 10000; timed = $false; writes_benchmark_result = $false }
            evidence = "v8-optimization-direct_first.txt"; evidence_sha256 = $evidenceHashes["v8-optimization-direct_first.txt"]
            findings = $javascriptOrderFindings.direct_first
        }
        function_call_first = [ordered]@{
            command = @("node", "--trace-opt", "--trace-deopt", "--trace-turbo-inlining", "tools/trace_function_call_javascript.js", "function_call_first")
            stimulus = [ordered]@{ iterations = 100; item_count = 10000; timed = $false; writes_benchmark_result = $false }
            evidence = "v8-optimization-function_call_first.txt"; evidence_sha256 = $evidenceHashes["v8-optimization-function_call_first.txt"]
            findings = $javascriptOrderFindings.function_call_first
        }
    }
    trace_is_benchmark = $false
    evidence_sha256 = $evidenceHashes
}
Write-Utf8 (Join-Path $artifactDir "provenance.json") (($provenance | ConvertTo-Json -Depth 5) + "`n")
$safety = Invoke-RecordedStage 'artifact-safety' 'python' @('tools/check_function_call_artifact_safety.py', $artifactDir) '' -AllowFailure
if ($safety.exit_code -ne 0) { throw 'artifact safety scan failed' }
$validation = Invoke-RecordedStage 'validator' 'python' @('tools/validate_function_call_analysis.py', $artifactDir, '--expected-sha', $gitSha) '' -AllowFailure
$validationResult = [ordered]@{ status = if ($validation.exit_code -eq 0) { 'valid' } else { 'invalid' }; exit_code = $validation.exit_code; output = Protect-ArtifactText $validation.stdout }
Write-Utf8 (Join-Path $artifactDir 'validation.json') (($validationResult | ConvertTo-Json -Depth 4) + "`n")
$script:runState.validation_json = 'validation.json'
Add-StageEvidence 'validator' (Join-Path $artifactDir 'validation.json')
if ($validation.exit_code -ne 0) { throw 'analysis package validation failed' }
$script:runState.status = 'success'
Write-RunState
Write-Host "status=success"
Write-Host "analysis_id=$AnalysisId"
} catch {
    if ($script:runState) {
        $script:runState.status = 'failed'
        $script:runState.error = Protect-ArtifactText $_.Exception.Message
        $validationPath = Join-Path $artifactDir 'validation.json'
        if (Test-Path -LiteralPath $validationPath) {
            $currentValidation = Get-Content -LiteralPath $validationPath -Raw | ConvertFrom-Json
            if ($currentValidation.status -eq 'pending') {
                Write-Utf8 $validationPath (([ordered]@{ status = 'not_completed'; reason = $script:runState.error } | ConvertTo-Json) + "`n")
            }
        }
        Write-RunState
    }
    throw
} finally {
    if ($null -ne $measurementLock) { $measurementLock.Dispose() }
    if ($null -ne $operationLock) { $operationLock.Dispose() }
}
