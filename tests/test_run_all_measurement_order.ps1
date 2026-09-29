$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $root 'benchmarks/function_call_numeric_sum/run_all.ps1'
$cOrderTest = Join-Path $root 'tests/test_c_measurement_order.ps1'
$benchmark = 'function_call_numeric_sum'
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$directId = "${timestamp}_${benchmark}"
$reverseTimestamp = (Get-Date).AddSeconds(2).ToString('yyyyMMdd_HHmmss')
$reuseTimestamp = (Get-Date).AddSeconds(4).ToString('yyyyMMdd_HHmmss')
$reverseId = "${reverseTimestamp}_${benchmark}"
$reuseId = "${reuseTimestamp}_${benchmark}"

function Get-OnlyArchive([string]$ExperimentId) {
    $parent = Join-Path $root "results/history/$ExperimentId"
    $archives = @(Get-ChildItem -LiteralPath $parent -Directory)
    if ($archives.Count -ne 1) { throw "Expected one archive for $ExperimentId; found $($archives.Count)." }
    return $archives[0].FullName
}

function Invoke-Run([string]$ExperimentId, [string]$Order = 'direct_first') {
    & $runner -ExperimentId $ExperimentId -MeasurementOrder $Order
    if ($LASTEXITCODE -ne 0) { throw "run_all failed for $ExperimentId ($Order)." }
}

Push-Location $root
try {
    & $cOrderTest
    if ($LASTEXITCODE -ne 0) { throw 'C measurement-order integration test failed.' }

    # Verify an existing reverse-order ID is rejected before Python or Node can rewrite raw files.
    $diagnostic = Join-Path $root "results/diagnostics/$reuseId"
    [System.IO.Directory]::CreateDirectory($diagnostic) | Out-Null
    $sentinels = @{}
    foreach ($language in @('python', 'javascript', 'c')) {
        $file = Join-Path $diagnostic "$language.json"
        $content = "preserve-$language-issue63"
        [System.IO.File]::WriteAllText($file, $content)
        $sentinels[$file] = $content
    }
    $failedAsExpected = $false
    try { Invoke-Run $reuseId 'function_call_first' }
    catch { $failedAsExpected = $_.Exception.Message -like '*output already exists*' }
    if (-not $failedAsExpected) { throw 'A reused reverse-order ExperimentId was not rejected during preflight.' }
    foreach ($entry in $sentinels.GetEnumerator()) {
        if ([System.IO.File]::ReadAllText($entry.Key) -cne $entry.Value) { throw "Existing diagnostic raw was modified: $($entry.Key)" }
    }

    Invoke-Run $directId
    Invoke-Run $reverseId 'function_call_first'
    $comparison = & python tools/compare_archives.py --json (Get-OnlyArchive $directId) (Get-OnlyArchive $reverseId)
    if ($LASTEXITCODE -ne 0) { throw 'Archive comparison command failed.' }
    $result = ($comparison -join "`n") | ConvertFrom-Json
    if ($result.verdict -ne 'incomparable' -or -not (@($result.reasons | Where-Object { $_.field -eq 'measurement_order' }).Count -gt 0)) {
        throw "Expected measurement-order incompatibility; got: $($comparison -join ' ')"
    }
} finally {
    Pop-Location
}

Write-Output 'run_all direct/reverse integration passed'
