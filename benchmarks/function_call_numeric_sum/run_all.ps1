param(
    [string]$ExperimentId
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
try {
    $pythonRunId = "$(New-TimestampId)_python_$benchmark"
    & python "benchmarks/function_call_numeric_sum/python/main.py" "--experiment-id=$ExperimentId" "--run-id=$pythonRunId"
    if ($LASTEXITCODE -ne 0) { throw "Python benchmark failed with exit code $LASTEXITCODE" }

    $javascriptRunId = "$(New-TimestampId)_javascript_$benchmark"
    & node "benchmarks/function_call_numeric_sum/javascript/main.js" "--experiment-id=$ExperimentId" "--run-id=$javascriptRunId"
    if ($LASTEXITCODE -ne 0) { throw "JavaScript benchmark failed with exit code $LASTEXITCODE" }

    $cRunId = "$(New-TimestampId)_c_$benchmark"
    & "benchmarks/function_call_numeric_sum/c/run_c.ps1" -ExperimentId $ExperimentId -RunId $cRunId
    if ($LASTEXITCODE -ne 0) { throw "C benchmark failed with exit code $LASTEXITCODE" }

    & python tools/validate_result_json.py `
        results/function_call_numeric_sum_python_result.json `
        results/function_call_numeric_sum_javascript_result.json `
        results/function_call_numeric_sum_c_result.json
    if ($LASTEXITCODE -ne 0) { throw "Result validation failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host "status=success"
Write-Host "experiment_id=$ExperimentId"
