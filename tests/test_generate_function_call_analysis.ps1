$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$generator = Join-Path $projectRoot 'tools/generate_function_call_analysis.ps1'
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("langbench-analysis-lock-test-" + [guid]::NewGuid().ToString('N'))

function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Invoke-ExpectedFailure([string]$AnalysisId, [string]$Output) {
    try { & $generator -AnalysisId $AnalysisId -OutputDirectory $Output -SharedRepositoryPath $sharedRoot -AllowedRemote $script:fixtureAllowedRemote 2>$null; return $false }
    catch { return $true }
}

try {
    [IO.Directory]::CreateDirectory($tempRoot) | Out-Null
    $sourceSha = (& git -C $projectRoot rev-parse HEAD).Trim()
    $detachedSource = Join-Path $tempRoot 'detached-source-checkout'
    & git clone --quiet --no-local $projectRoot $detachedSource
    if ($LASTEXITCODE -ne 0) { throw 'failed to create detached source fixture' }
    & git -C $detachedSource switch --quiet --detach $sourceSha
    if ($LASTEXITCODE -ne 0 -or (& git -C $detachedSource symbolic-ref --quiet --short HEAD)) { throw 'source fixture is not detached' }
    $sharedRoot = Join-Path $tempRoot 'user-working-copy'
    & git clone --quiet --no-local --no-checkout $detachedSource $sharedRoot
    if ($LASTEXITCODE -ne 0) { throw 'failed to create independent shared-lock fixture clone' }
    $existingMain = @(& git -C $sharedRoot show-ref --verify --quiet refs/heads/main)
    if ($LASTEXITCODE -eq 0) { & git -C $sharedRoot switch --quiet main }
    else { & git -C $sharedRoot switch --quiet -c main $sourceSha }
    if ($LASTEXITCODE -ne 0) { throw 'failed to prepare shared main fixture' }
    if ((& git -C $sharedRoot rev-parse HEAD).Trim() -ne $sourceSha) { throw 'shared fixture SHA differs from source checkout' }
    $sharedBranch = @(& git -C $sharedRoot symbolic-ref --quiet --short HEAD)
    if ($LASTEXITCODE -ne 0 -or $sharedBranch.Count -ne 1 -or $sharedBranch[0] -ne 'main') { throw 'shared fixture is not on main' }
    $script:fixtureAllowedRemote = $detachedSource
    $gitDirectory = (& git -C $sharedRoot rev-parse --path-format=absolute --git-common-dir).Trim()
    $lockPath = Join-Path $gitDirectory 'langbench-operation.lock'
    & git -C $sharedRoot switch --quiet --detach $sourceSha
    $detachedOutput = Join-Path $tempRoot 'detached-shared-output'
    Assert-True (Invoke-ExpectedFailure 'detached-shared' $detachedOutput) 'detached shared repository unexpectedly succeeded'
    Assert-True (-not (Test-Path -LiteralPath $detachedOutput)) 'detached shared repository created output'
    & git -C $sharedRoot switch --quiet main
    if ($LASTEXITCODE -ne 0) { throw 'failed to restore shared fixture main' }
    $releasedAfterDetached = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    $releasedAfterDetached.Dispose()
    $blockedOutput = Join-Path $tempRoot 'blocked-output'
    $lock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        Assert-True (Invoke-ExpectedFailure 'lock-conflict' $blockedOutput) 'analysis unexpectedly acquired the shared operation lock'
        Assert-True (-not (Test-Path -LiteralPath $blockedOutput)) 'blocked analysis created output'
    } finally { $lock.Dispose() }

    $measurementLockPath = Join-Path $sharedRoot 'results/function_call_numeric_sum.lock'
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
    try { & $generator -AnalysisId partial-failure -OutputDirectory $partialOutput -SharedRepositoryPath $sharedRoot -AllowedRemote $script:fixtureAllowedRemote -TestFailTraceOrder function_call_first; $failed = $false }
    catch { $failed = $true }
    Assert-True $failed 'second trace fixture unexpectedly succeeded'
    $firstTrace = Get-Content -LiteralPath (Join-Path $partialOutput 'v8-optimization-direct_first.txt') -Raw
    $secondTrace = Get-Content -LiteralPath (Join-Path $partialOutput 'v8-optimization-function_call_first.txt') -Raw
    Assert-True ($firstTrace -match '# exit_code=0') 'successful first trace was not retained'
    Assert-True ($secondTrace -match '# exit_code=23' -and $secondTrace -match 'partial stdout' -and $secondTrace -match 'fixture failure') 'failed trace diagnostics were not retained'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $partialOutput 'manifest.json'))) 'partial analysis produced a success manifest'
    $releasedAgain = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    $releasedAgain.Dispose()
    Write-Host 'tests=5 passed=5'
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
