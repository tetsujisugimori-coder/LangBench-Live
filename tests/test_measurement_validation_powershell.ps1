$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $root 'tools/run_measurement_validation.ps1'
$errors = $null
[void][Management.Automation.Language.Parser]::ParseFile($script, [ref]$null, [ref]$errors)
if (@($errors).Count) { throw ($errors | ForEach-Object Message | Out-String) }

$fixture = Join-Path $env:RUNNER_TEMP "measurement-validation-fixture-$([guid]::NewGuid().ToString('N'))"
$bare = Join-Path $fixture 'remote.git'; $shared = Join-Path $fixture 'shared'
New-Item -ItemType Directory -Path $fixture | Out-Null
try {
    $sha = (& git -C $root rev-parse HEAD).Trim()
    & git clone --bare $root $bare | Out-Null
    & git --git-dir=$bare branch -f main $sha
    & git clone --branch main $bare $shared | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $shared 'results') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $shared 'fixture-untracked.txt') -Value 'preserve me' -Encoding utf8
    $before = (Get-FileHash -LiteralPath (Join-Path $shared 'fixture-untracked.txt') -Algorithm SHA256).Hash
    $common = (& git -C $shared rev-parse --path-format=absolute --git-common-dir).Trim()
    $marker = Join-Path $common 'MERGE_HEAD'
    Set-Content -LiteralPath $marker -Value $sha -Encoding ascii
    try {
        & $script -TrustedSha $sha -SyncRunId 1 -RunId 1 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-marker') `
            -ExecutionDirectory (Join-Path $fixture 'exec-marker') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
        throw 'Git marker fixture unexpectedly succeeded'
    } catch { if ($_ -notmatch 'Git operation in progress') { throw } }
    Remove-Item -LiteralPath $marker -Force

    $existingExecution = Join-Path $fixture 'exec-collision'; New-Item -ItemType Directory -Path $existingExecution | Out-Null
    try {
        & $script -TrustedSha $sha -SyncRunId 1 -RunId 4 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-collision') `
            -ExecutionDirectory $existingExecution -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
        throw 'execution collision fixture unexpectedly succeeded'
    } catch { if ($_ -notmatch 'execution directory already exists') { throw } }
    $existingOutput = Join-Path $fixture 'output-collision'; New-Item -ItemType Directory -Path $existingOutput | Out-Null
    try {
        & $script -TrustedSha $sha -SyncRunId 1 -RunId 5 -RunAttempt 1 -OutputDirectory $existingOutput `
            -ExecutionDirectory (Join-Path $fixture 'exec-unused') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
        throw 'output collision fixture unexpectedly succeeded'
    } catch { if ($_ -notmatch 'output already exists') { throw } }

    $measurement = [IO.File]::Open((Join-Path $shared 'results/function_call_numeric_sum.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        try {
            & $script -TrustedSha $sha -SyncRunId 1 -RunId 2 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-lock') `
                -ExecutionDirectory (Join-Path $fixture 'exec-lock') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
            throw 'measurement lock fixture unexpectedly succeeded'
        } catch { if ($_ -notmatch 'used by another process') { throw } }
    } finally { $measurement.Dispose() }

    $env:LANGBENCH_TEST_PREFLIGHT = '1'
    & $script -TrustedSha $sha -SyncRunId 1 -RunId 3 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-ok') `
        -ExecutionDirectory (Join-Path $fixture 'exec-ok') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
    if ($LASTEXITCODE -ne 0 -or (Get-FileHash -LiteralPath (Join-Path $shared 'fixture-untracked.txt') -Algorithm SHA256).Hash -ne $before) {
        throw 'preflight fixture did not preserve untracked data'
    }
} finally {
    $env:LANGBENCH_TEST_PREFLIGHT = $null
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
Write-Host 'measurement validation PowerShell fixtures: valid'
