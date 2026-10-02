$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $root 'tools/run_measurement_validation.ps1'
$errors = $null
[void][Management.Automation.Language.Parser]::ParseFile($script, [ref]$null, [ref]$errors)
if (@($errors).Count) { throw ($errors | ForEach-Object Message | Out-String) }
function G {
    $output = & git.exe @args
    if ($LASTEXITCODE -ne 0) { throw "fixture git failed ($LASTEXITCODE): $($args -join ' ')" }
    return $output
}

$fixture = Join-Path $env:RUNNER_TEMP "measurement-validation-fixture-$([guid]::NewGuid().ToString('N'))"
$bare = Join-Path $fixture 'remote.git'; $shared = Join-Path $fixture 'shared'
$oldGitConfigGlobal = $env:GIT_CONFIG_GLOBAL
New-Item -ItemType Directory -Path $fixture | Out-Null
try {
    $env:LANGBENCH_TEST_PREFLIGHT = '1'
    $sha = (G -C $root rev-parse HEAD).Trim()
    G clone --bare $root $bare | Out-Null
    G --git-dir=$bare branch -f main $sha | Out-Null
    G clone --branch main $bare $shared | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $shared 'results') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $shared 'fixture-untracked.txt') -Value 'preserve me' -Encoding utf8
    Set-Content -LiteralPath (Join-Path $shared 'results/function_call_numeric_sum_python_result.json') -Value 'ignored raw' -Encoding utf8
    $before = (Get-FileHash -LiteralPath (Join-Path $shared 'fixture-untracked.txt') -Algorithm SHA256).Hash
    $rawBefore = (Get-FileHash -LiteralPath (Join-Path $shared 'results/function_call_numeric_sum_python_result.json') -Algorithm SHA256).Hash
    $common = (G -C $shared rev-parse --path-format=absolute --git-common-dir).Trim()
    $marker = Join-Path $common 'MERGE_HEAD'
    Set-Content -LiteralPath $marker -Value $sha -Encoding ascii
    try {
        & $script -TrustedSha $sha -SyncRunId 1 -RunId 1 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-marker') `
            -ExecutionDirectory (Join-Path $fixture 'exec-marker') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
        throw 'Git marker fixture unexpectedly succeeded'
    } catch { if ($_ -notmatch 'Git operation in progress') { throw } }
    Remove-Item -LiteralPath $marker -Force

    G -C $shared config filter.fixture.process 'fixture-arbitrary-process' | Out-Null
    try {
        & $script -TrustedSha $sha -SyncRunId 1 -RunId 7 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-filter') `
            -ExecutionDirectory (Join-Path $fixture 'exec-filter') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
        throw 'dangerous filter fixture unexpectedly succeeded'
    } catch { if ($_ -notmatch 'effective Git filter is refused') { throw } }
    G -C $shared config --unset-all filter.fixture.process | Out-Null

    Add-Content -LiteralPath (Join-Path $shared 'README.md') -Value 'fixture dirty'
    try {
        & $script -TrustedSha $sha -SyncRunId 1 -RunId 8 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-dirty') `
            -ExecutionDirectory (Join-Path $fixture 'exec-dirty') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
        throw 'dirty fixture unexpectedly succeeded'
    } catch { if ($_ -notmatch 'tracked changes') { throw } }
    G -C $shared checkout -- README.md | Out-Null

    G -C $shared checkout --detach $sha | Out-Null
    try {
        & $script -TrustedSha $sha -SyncRunId 1 -RunId 9 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-head') `
            -ExecutionDirectory (Join-Path $fixture 'exec-head') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
        throw 'HEAD mismatch fixture unexpectedly succeeded'
    } catch { if ($_ -notmatch 'not on main') { throw } }
    G -C $shared checkout main | Out-Null

    G -C $shared checkout -b fixture-other | Out-Null
    Add-Content -LiteralPath (Join-Path $shared 'README.md') -Value 'fixture alternate commit'
    G -C $shared -c user.name=fixture -c user.email=fixture@example.invalid commit -am 'fixture alternate commit' | Out-Null
    $otherSha = (G -C $shared rev-parse HEAD).Trim()
    G -C $shared branch -f main $otherSha | Out-Null
    G -C $shared checkout main | Out-Null
    try {
        & $script -TrustedSha $sha -SyncRunId 1 -RunId 11 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-head-mismatch') `
            -ExecutionDirectory (Join-Path $fixture 'exec-head-mismatch') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
        throw 'main HEAD mismatch fixture unexpectedly succeeded'
    } catch { if ($_ -notmatch 'not the authorized SHA') { throw } }
    G -C $shared checkout fixture-other | Out-Null
    G -C $shared branch -f main $sha | Out-Null
    G -C $shared checkout main | Out-Null
    G -C $shared branch -D fixture-other | Out-Null

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

    $operation = [IO.File]::Open((Join-Path $common 'langbench-operation.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        try {
            & $script -TrustedSha $sha -SyncRunId 1 -RunId 10 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-operation-lock') `
                -ExecutionDirectory (Join-Path $fixture 'exec-operation-lock') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
            throw 'operation lock fixture unexpectedly succeeded'
        } catch { if ($_ -notmatch 'used by another process') { throw } }
    } finally { $operation.Dispose() }

    & $script -TrustedSha $sha -SyncRunId 1 -RunId 3 -RunAttempt 1 -OutputDirectory (Join-Path $fixture 'out-ok') `
        -ExecutionDirectory (Join-Path $fixture 'exec-ok') -SharedRepositoryPath $shared -AllowedRemote @($bare) -TestPreflightOnly
    if ($LASTEXITCODE -ne 0 -or (Get-FileHash -LiteralPath (Join-Path $shared 'fixture-untracked.txt') -Algorithm SHA256).Hash -ne $before -or
        (Get-FileHash -LiteralPath (Join-Path $shared 'results/function_call_numeric_sum_python_result.json') -Algorithm SHA256).Hash -ne $rawBefore) {
        throw 'preflight fixture did not preserve untracked data'
    }
    $env:LANGBENCH_HOSTED_FIXTURE = '1'
    $globalConfig = Join-Path $fixture 'fixture-global.gitconfig'
    $globalAttributes = Join-Path $fixture 'fixture-global-attributes'
    $filterScript = Join-Path $fixture 'fixture-smudge.py'
    $filterMarker = Join-Path $fixture 'filter-executed.txt'
    Set-Content -LiteralPath $globalAttributes -Value '* filter=lfs' -Encoding ascii
    @"
import pathlib, sys
data = sys.stdin.buffer.read()
pathlib.Path(r'$filterMarker').write_text('executed', encoding='utf-8')
sys.stdout.buffer.write(data + b'changed-by-unsafe-filter')
"@ | Set-Content -LiteralPath $filterScript -Encoding utf8
    G config --file $globalConfig core.attributesFile $globalAttributes | Out-Null
    G config --file $globalConfig filter.lfs.smudge "python `"$filterScript`"" | Out-Null
    G config --file $globalConfig filter.lfs.required true | Out-Null
    $env:GIT_CONFIG_GLOBAL = $globalConfig
    $failedOutput = Join-Path $fixture 'out-generation-failure'
    $failedExecution = Join-Path $fixture 'exec-generation-failure'
    try {
        & $script -TrustedSha $sha -SyncRunId 1 -RunId 6 -RunAttempt 1 -OutputDirectory $failedOutput `
            -ExecutionDirectory $failedExecution -SharedRepositoryPath $shared `
            -AllowedRemote @($bare) -TestFailureStage generation
        throw 'generation failure fixture unexpectedly succeeded'
    } catch { if ($_ -notmatch 'Count=1 measurement failed with exit code 23') { throw } }
    if (Test-Path -LiteralPath (Join-Path $failedOutput 'files.sha256.json')) { throw 'failed generation produced a successful bundle' }
    if (Test-Path -LiteralPath $filterMarker) { throw 'global smudge filter executed during independent checkout' }
    $expectedBlob = (G -C $root show "${sha}:README.md") -join "`n"
    $actualBlob = (Get-Content -LiteralPath (Join-Path $failedExecution 'README.md') -Raw).Replace("`r`n", "`n").TrimEnd("`n")
    if ($actualBlob -cne $expectedBlob) { throw 'independent checkout tracked blob differs from trusted Git blob' }
} finally {
    $env:LANGBENCH_TEST_PREFLIGHT = $null
    $env:LANGBENCH_HOSTED_FIXTURE = $null
    $env:GIT_CONFIG_GLOBAL = $oldGitConfigGlobal
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
Write-Host 'measurement validation PowerShell fixtures: valid'
