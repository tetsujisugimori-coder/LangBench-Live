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
    $partialState = Get-Content -LiteralPath (Join-Path $partialOutput 'run-state.json') -Raw | ConvertFrom-Json
    $partialValidation = Get-Content -LiteralPath (Join-Path $partialOutput 'validation.json') -Raw | ConvertFrom-Json
    Assert-True ($partialState.status -eq 'failed' -and $partialState.stages.'node-trace-direct_first'.status -eq 'success' -and $partialState.stages.'node-trace-function_call_first'.status -eq 'failed') 'partial stage state was not retained'
    Assert-True ($partialState.stages.'node-trace-function_call_first'.exit_code -eq 23) 'failed stage exit code was not recorded'
    Assert-True ($partialValidation.status -eq 'not_completed') 'partial validation state was not retained'
    Assert-True (Test-Path -LiteralPath (Join-Path $partialOutput 'stage-logs/node-trace-function_call_first.stderr.txt')) 'failed stage stderr log was not retained'
    & python -B (Join-Path $projectRoot 'tools/check_function_call_artifact_safety.py') $partialOutput
    Assert-True ($LASTEXITCODE -eq 0) 'partial artifact contains a secret or local absolute path'
    $dummySource = Join-Path $tempRoot 'dummy-gcc.c'
    $dummyExe = Join-Path $tempRoot 'dummy-gcc.exe'
    [IO.File]::WriteAllText($dummySource, @'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "--version") == 0) { puts("gcc fixture 1.0"); return 0; }
    const char *report = NULL, *assembly = NULL;
    for (int i = 1; i < argc; ++i) {
        if (strncmp(argv[i], "-fopt-info-all=", 15) == 0) report = argv[i] + 15;
        if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) assembly = argv[++i];
    }
    if (!report || !assembly) return 24;
    FILE *file = fopen(report, "wb");
    if (!file) return 25;
    fputs("D:/a/private ghp_abcdefghijklmnopqrst\n", file); fclose(file);
    file = fopen(assembly, "wb");
    if (!file) return 26;
    fputs("secret=dummyvalue\n", file); fclose(file);
    fputs("fixture compiler stopped\n", stderr);
    return 23;
}
'@, [Text.UTF8Encoding]::new($false))
    & gcc -x c $dummySource -o $dummyExe
    if ($LASTEXITCODE -ne 0) { throw 'dummy GCC fixture compile failed' }
    $gccFailureOutput = Join-Path $tempRoot 'gcc-failure-output'
    try { & $generator -AnalysisId gcc-failure -OutputDirectory $gccFailureOutput -SharedRepositoryPath $sharedRoot -AllowedRemote $script:fixtureAllowedRemote -GccExecutable $dummyExe; $gccFailed = $false }
    catch { $gccFailed = $true }
    Assert-True $gccFailed 'dummy GCC failure unexpectedly succeeded'
    $gccState = Get-Content -LiteralPath (Join-Path $gccFailureOutput 'run-state.json') -Raw | ConvertFrom-Json
    Assert-True ($gccState.status -eq 'failed' -and $gccState.stages.gcc.exit_code -eq 23) 'GCC failure state or exit code was lost'
    Assert-True ((Get-Content -LiteralPath (Join-Path $gccFailureOutput 'gcc-optimization.txt') -Raw) -match 'ghp_') 'raw GCC failure evidence was not retained locally'
    $gccBundle = Join-Path $tempRoot 'gcc-failure-upload'
    & python -B (Join-Path $projectRoot 'tools/prepare_function_call_analysis_upload.py') $gccFailureOutput $gccBundle
    Assert-True ($LASTEXITCODE -eq 0) 'GCC failure upload bundle preparation failed'
    $safeReport = Get-Content -LiteralPath (Join-Path $gccBundle 'gcc-optimization.txt') -Raw
    $safeAssembly = Get-Content -LiteralPath (Join-Path $gccBundle 'main.s') -Raw
    Assert-True ($safeReport -match '<redacted-absolute-path>' -and $safeReport -match '<redacted-credential>') 'GCC report was not sanitized'
    Assert-True ($safeAssembly -match '<redacted-credential>') 'GCC assembly was not sanitized'
    Assert-True (Test-Path -LiteralPath (Join-Path $gccBundle 'run-state.json')) 'safe GCC failure state was not retained'
    Assert-True (Test-Path -LiteralPath (Join-Path $gccBundle 'stage-logs/gcc.stderr.txt')) 'safe GCC failure log was not retained'
    & python -B (Join-Path $projectRoot 'tools/check_function_call_artifact_safety.py') $gccBundle
    Assert-True ($LASTEXITCODE -eq 0) 'GCC failure bundle was not safe'
    $releasedAgain = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    $releasedAgain.Dispose()
    Write-Host 'tests=6 passed=6'
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
