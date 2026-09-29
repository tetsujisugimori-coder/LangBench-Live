param(
    [string]$ExperimentId,
    [ValidateSet('direct_first', 'function_call_first')][string]$MeasurementOrder = 'direct_first'
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$benchmark = "function_call_numeric_sum"

function New-TimestampId {
    return Get-Date -Format "yyyyMMdd_HHmmss"
}

if ([string]::IsNullOrWhiteSpace($ExperimentId)) {
    $ExperimentId = "$(New-TimestampId)_$benchmark"
}

Push-Location $projectRoot
$lock = $null
try {
    # Staging files still have fixed names, so only one full run may use them at a time.
    [System.IO.Directory]::CreateDirectory((Join-Path $projectRoot "results")) | Out-Null
    $lock = [System.IO.File]::Open(
        (Join-Path $projectRoot "results/function_call_numeric_sum.lock"),
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
    $pythonRunId = "$(New-TimestampId)_python_$benchmark"
    $resultPaths = @(
        'results/function_call_numeric_sum_python_result.json',
        'results/function_call_numeric_sum_javascript_result.json',
        'results/function_call_numeric_sum_c_result.json'
    )
    if ($MeasurementOrder -eq 'function_call_first') {
        $diagnosticDirectory = Join-Path $projectRoot "results/diagnostics/$ExperimentId"
        # A diagnostic run is immutable: reject a reused ID before any language starts.
        if (Test-Path -LiteralPath $diagnosticDirectory) {
            throw "Diagnostic output already exists; choose a new ExperimentId: $diagnosticDirectory"
        }
        [System.IO.Directory]::CreateDirectory($diagnosticDirectory) | Out-Null
        $resultPaths = @('python', 'javascript', 'c') | ForEach-Object { Join-Path $diagnosticDirectory "$_.json" }
    }
    $pythonArguments = @("--experiment-id=$ExperimentId", "--run-id=$pythonRunId", "--measurement-order=$MeasurementOrder")
    if ($MeasurementOrder -eq 'function_call_first') { $pythonArguments += @("--result-path=$($resultPaths[0])", '--exclusive-result') }
    & python "benchmarks/function_call_numeric_sum/python/main.py" @pythonArguments
    if ($LASTEXITCODE -ne 0) { throw "Python benchmark failed with exit code $LASTEXITCODE" }

    $javascriptRunId = "$(New-TimestampId)_javascript_$benchmark"
    $javascriptArguments = @("--experiment-id=$ExperimentId", "--run-id=$javascriptRunId", "--measurement-order=$MeasurementOrder")
    if ($MeasurementOrder -eq 'function_call_first') { $javascriptArguments += @("--result-path=$($resultPaths[1])", '--exclusive-result') }
    & node "benchmarks/function_call_numeric_sum/javascript/main.js" @javascriptArguments
    if ($LASTEXITCODE -ne 0) { throw "JavaScript benchmark failed with exit code $LASTEXITCODE" }

    $cRunId = "$(New-TimestampId)_c_$benchmark"
    $cArguments = @{ ExperimentId = $ExperimentId; RunId = $cRunId; MeasurementOrder = $MeasurementOrder }
    if ($MeasurementOrder -eq 'function_call_first') { $cArguments.DiagnosticResultPath = $resultPaths[2] }
    & "benchmarks/function_call_numeric_sum/c/run_c.ps1" @cArguments
    if ($LASTEXITCODE -ne 0) { throw "C benchmark failed with exit code $LASTEXITCODE" }

    & python tools/validate_result_json.py `
        $resultPaths[0] $resultPaths[1] $resultPaths[2]
    if ($LASTEXITCODE -ne 0) { throw "Result validation failed with exit code $LASTEXITCODE" }

    & python tools/archive_results.py --experiment-id $ExperimentId `
        $resultPaths[0] $resultPaths[1] $resultPaths[2]
    if ($LASTEXITCODE -ne 0) { throw "Result archival failed with exit code $LASTEXITCODE" }
} finally {
    if ($null -ne $lock) { $lock.Dispose() }
    Pop-Location
}

Write-Host "status=success"
Write-Host "experiment_id=$ExperimentId"
