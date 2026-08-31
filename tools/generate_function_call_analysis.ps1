param([string]$AnalysisId)

$ErrorActionPreference = "Stop"

function Invoke-CapturedProcess {
    param([string]$FileName, [string[]]$Arguments, [string]$WorkingDirectory)
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $FileName
    $info.WorkingDirectory = $WorkingDirectory
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    foreach ($argument in $Arguments) { $info.ArgumentList.Add($argument) }
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $info
    if (-not $process.Start()) { throw "failed to start $FileName" }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    if ($process.ExitCode -ne 0) { throw "$FileName failed with exit code $($process.ExitCode): $stderr" }
    return [ordered]@{ stdout = $stdout; stderr = $stderr }
}

function Write-Utf8 {
    param([string]$Path, [string]$Content)
    [System.IO.File]::WriteAllText($Path, $Content.Replace("`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactDir = Join-Path $projectRoot "artifacts\function-call-analysis"
[System.IO.Directory]::CreateDirectory($artifactDir) | Out-Null
$cSource = Join-Path $projectRoot "benchmarks\function_call_numeric_sum\c\main.c"
$pythonSource = Join-Path $projectRoot "benchmarks\function_call_numeric_sum\python\main.py"
$javascriptSource = Join-Path $projectRoot "benchmarks\function_call_numeric_sum\javascript\main.js"
$gccReport = Join-Path $artifactDir "gcc-optimization.txt"
$assembly = Join-Path $artifactDir "main.s"
$pythonBytecode = Join-Path $artifactDir "python-bytecode.txt"
$v8Trace = Join-Path $artifactDir "v8-optimization.txt"
$manifestPath = Join-Path $artifactDir "manifest.json"
$analyzedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
if ([string]::IsNullOrWhiteSpace($AnalysisId)) { $AnalysisId = "function-call-analysis-" + (Get-Date -Format "yyyyMMdd-HHmmss") }

$gccVersionOutput = Invoke-CapturedProcess "gcc" @("--version") $projectRoot
$gccVersion = ($gccVersionOutput.stdout -split "`r?`n")[0]
if ([string]::IsNullOrWhiteSpace($gccVersion)) { throw "failed to obtain GCC version" }
$gccVersion = $gccVersion -replace '^gcc\.exe ', 'gcc '
$cOptions = @("-O2", "-std=c11", "-Wall", "-Wextra")
Remove-Item -LiteralPath $gccReport, $assembly -Force -ErrorAction SilentlyContinue
$gccArgs = @($cSource) + $cOptions + @("-S", "-masm=intel", "-fopt-info-all=$gccReport", "-o", $assembly)
& gcc @gccArgs
if ($LASTEXITCODE -ne 0) { throw "GCC analysis failed with exit code $LASTEXITCODE" }

$pythonInfo = (Invoke-CapturedProcess "python" @("-c", "import json,platform; print(json.dumps({'name': platform.python_implementation(), 'version': platform.python_version(), 'architecture': platform.machine().lower()}))") $projectRoot).stdout | ConvertFrom-Json
$pythonDis = Invoke-CapturedProcess "python" @("-m", "dis", $pythonSource) $projectRoot
if (-not [string]::IsNullOrWhiteSpace($pythonDis.stderr)) { throw "Python disassembly wrote to stderr: $($pythonDis.stderr)" }
Write-Utf8 $pythonBytecode $pythonDis.stdout

$nodeInfo = (Invoke-CapturedProcess "node" @("-p", "JSON.stringify({node:process.version,v8:process.versions.v8,architecture:require('os').arch()})") $projectRoot).stdout | ConvertFrom-Json
$traceArgs = @("--trace-opt", "--trace-deopt", "--trace-turbo-inlining", $javascriptSource, "--experiment-id=20000101_000000_function_call_numeric_sum", "--run-id=20000101_000000_javascript_function_call_numeric_sum")
$nodeTrace = Invoke-CapturedProcess "node" $traceArgs $projectRoot
$traceStdout = (($nodeTrace.stdout -split "`r?`n") | Where-Object { $_ -and $_ -notmatch '^status=' }) -join "`n"
$traceStderr = (($nodeTrace.stderr -split "`r?`n") | Where-Object { $_ }) -join "`n"
$traceContent = "# stdout`n$traceStdout`n# stderr"
if ($traceStderr) {
    $traceContent += "`n$traceStderr"
}
Write-Utf8 $v8Trace ("$traceContent`n")

$architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
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
                source_sha256 = (Get-FileHash -LiteralPath $cSource -Algorithm SHA256).Hash.ToLowerInvariant()
                implementation = [ordered]@{ name = "GCC"; version = $gccVersion }
                architecture = $architecture
                options = $cOptions
            }
            generation_commands = @(
                @("gcc", "benchmarks/function_call_numeric_sum/c/main.c") + $cOptions + @("-S", "-masm=intel", "-fopt-info-all=artifacts/function-call-analysis/gcc-optimization.txt", "-o", "artifacts/function-call-analysis/main.s")
            )
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
                source_sha256 = (Get-FileHash -LiteralPath $pythonSource -Algorithm SHA256).Hash.ToLowerInvariant()
                implementation = [ordered]@{ name = $pythonInfo.name; version = $pythonInfo.version }
                architecture = $pythonInfo.architecture
                options = @("optimize=0")
            }
            generation_commands = @(@("python", "-m", "dis", "benchmarks/function_call_numeric_sum/python/main.py"))
            evidence = @([ordered]@{ type = "disassembly"; path = "artifacts/function-call-analysis/python-bytecode.txt" })
        }
        javascript = [ordered]@{
            artifact_id = "$AnalysisId-javascript"
            analyzed_at = $analyzedAt
            applies_to = @("jit", "inlining", "vectorization", "simd")
            condition = [ordered]@{
                source_sha256 = (Get-FileHash -LiteralPath $javascriptSource -Algorithm SHA256).Hash.ToLowerInvariant()
                implementation = [ordered]@{ name = "V8"; version = $nodeInfo.v8 }
                architecture = $nodeInfo.architecture
                options = @()
            }
            generation_commands = @(@("node", "--trace-opt", "--trace-deopt", "--trace-turbo-inlining", "benchmarks/function_call_numeric_sum/javascript/main.js"))
            runtime = [ordered]@{ name = "Node.js"; version = $nodeInfo.node }
            evidence = @([ordered]@{ type = "jit_trace"; path = "artifacts/function-call-analysis/v8-optimization.txt" })
        }
    }
}
Write-Utf8 $manifestPath (($manifest | ConvertTo-Json -Depth 12) + "`n")
Write-Host "status=success"
Write-Host "analysis_id=$AnalysisId"
