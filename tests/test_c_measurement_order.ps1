$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $projectRoot 'benchmarks/function_call_numeric_sum/c/run_c.ps1'
$validator = Join-Path $projectRoot 'tools/validate_result_json.py'
$diagnosticValidator = Join-Path $projectRoot 'tools/summarize_c_order_diagnostic.py'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('langbench-c-order-test-' + [guid]::NewGuid().ToString('N'))
[System.IO.Directory]::CreateDirectory($tempRoot) | Out-Null
$normalPath = Join-Path $projectRoot 'results/function_call_numeric_sum_c_result.json'
$historyPath = Join-Path $projectRoot 'results/history'
$normalHashBefore = if (Test-Path -LiteralPath $normalPath) { (Get-FileHash -LiteralPath $normalPath -Algorithm SHA256).Hash } else { $null }
$historyBefore = if (Test-Path -LiteralPath $historyPath) { @((Get-ChildItem -LiteralPath $historyPath -Recurse -File | ForEach-Object FullName) | Sort-Object) } else { @() }

function Assert-True { param([bool]$Condition, [string]$Message) if (-not $Condition) { throw $Message } }
try {
    foreach ($order in @('direct_first', 'function_call_first')) {
        $path = Join-Path $tempRoot "$order.json"
        $trace = Join-Path $tempRoot "$order-trace.json"
        & $runner -MeasurementOrder $order -DiagnosticResultPath $path -DiagnosticTracePath $trace | Out-Null
        Assert-True ($LASTEXITCODE -eq 0) "$order runner failed"
        & python -B $diagnosticValidator --validate-result $path --validate-trace $trace
        Assert-True ($LASTEXITCODE -eq 0) "$order diagnostic validation failed"
        $document = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        $expected = if ($order -eq 'direct_first') { @('direct', 'function_call') } else { @('function_call', 'direct') }
        Assert-True ((@($document.execution.measurement_order) -join ',') -eq ($expected -join ',')) "$order recorded wrong execution order"
        foreach ($case in @('direct', 'function_call')) {
            Assert-True (@($document.results.$case.samples_ms).Count -eq 50) "$order $case did not have 50 samples"
            Assert-True ($document.validation."${case}_checksum" -eq 500000500000) "$order $case checksum differed"
        }
        & python -B $validator $path *> $null
        if ($order -eq 'direct_first') { Assert-True ($LASTEXITCODE -eq 0) 'A was rejected by normal validator' }
        else { Assert-True ($LASTEXITCODE -ne 0) 'B entered normal validator' }
    }
    $normalHashAfter = if (Test-Path -LiteralPath $normalPath) { (Get-FileHash -LiteralPath $normalPath -Algorithm SHA256).Hash } else { $null }
    $historyAfter = if (Test-Path -LiteralPath $historyPath) { @((Get-ChildItem -LiteralPath $historyPath -Recurse -File | ForEach-Object FullName) | Sort-Object) } else { @() }
    Assert-True ($normalHashBefore -eq $normalHashAfter) 'Diagnostic C run modified the normal result.'
    Assert-True (($historyBefore -join "`n") -eq ($historyAfter -join "`n")) 'Diagnostic C run modified normal history.'
    Write-Host 'tests=2 passed=2'
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
