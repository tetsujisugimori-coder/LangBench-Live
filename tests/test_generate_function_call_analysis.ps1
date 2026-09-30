$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$generator = Join-Path $projectRoot 'tools/generate_function_call_analysis.ps1'
$gitDirectory = (& git -C $projectRoot rev-parse --path-format=absolute --git-common-dir).Trim()
$lockPath = Join-Path $gitDirectory 'langbench-operation.lock'
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("langbench-analysis-lock-test-" + [guid]::NewGuid().ToString('N'))

function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Invoke-ExpectedFailure([string]$AnalysisId, [string]$Output) {
    try { & $generator -AnalysisId $AnalysisId -OutputDirectory $Output 2>$null; return $false }
    catch { return $true }
}

try {
    [IO.Directory]::CreateDirectory($tempRoot) | Out-Null
    $blockedOutput = Join-Path $tempRoot 'blocked-output'
    $lock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        Assert-True (Invoke-ExpectedFailure 'lock-conflict' $blockedOutput) 'analysis unexpectedly acquired the shared operation lock'
        Assert-True (-not (Test-Path -LiteralPath $blockedOutput)) 'blocked analysis created output'
    } finally { $lock.Dispose() }

    $measurementLockPath = Join-Path $projectRoot 'results/function_call_numeric_sum.lock'
    $measurementLock = [IO.File]::Open($measurementLockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $measurementBlockedOutput = Join-Path $tempRoot 'measurement-blocked-output'
        Assert-True (Invoke-ExpectedFailure 'measurement-lock-conflict' $measurementBlockedOutput) 'analysis ignored the measurement lock'
        Assert-True (-not (Test-Path -LiteralPath $measurementBlockedOutput)) 'measurement-blocked analysis created output'
    } finally { $measurementLock.Dispose() }

    $existingOutput = Join-Path $tempRoot 'existing-output'
    [IO.Directory]::CreateDirectory($existingOutput) | Out-Null
    Assert-True (Invoke-ExpectedFailure 'forced-failure' $existingOutput) 'existing output unexpectedly succeeded'
    $released = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    $released.Dispose()

    $partialOutput = Join-Path $tempRoot 'partial-output'
    try { & $generator -AnalysisId partial-failure -OutputDirectory $partialOutput -TestFailTraceOrder function_call_first; $failed = $false }
    catch { $failed = $true }
    Assert-True $failed 'second trace fixture unexpectedly succeeded'
    $firstTrace = Get-Content -LiteralPath (Join-Path $partialOutput 'v8-optimization-direct_first.txt') -Raw
    $secondTrace = Get-Content -LiteralPath (Join-Path $partialOutput 'v8-optimization-function_call_first.txt') -Raw
    Assert-True ($firstTrace -match '# exit_code=0') 'successful first trace was not retained'
    Assert-True ($secondTrace -match '# exit_code=23' -and $secondTrace -match 'partial stdout' -and $secondTrace -match 'fixture failure') 'failed trace diagnostics were not retained'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $partialOutput 'manifest.json'))) 'partial analysis produced a success manifest'
    $releasedAgain = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    $releasedAgain.Dispose()
    Write-Host 'tests=4 passed=4'
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
