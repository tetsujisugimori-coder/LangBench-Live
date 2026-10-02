param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$TrustedSha,
    [Parameter(Mandatory)][ValidateRange(1, [long]::MaxValue)][long]$SyncRunId,
    [Parameter(Mandatory)][ValidateRange(1, [long]::MaxValue)][long]$RunId,
    [Parameter(Mandatory)][ValidateRange(1, [int]::MaxValue)][int]$RunAttempt,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [Parameter(Mandatory)][string]$ExecutionDirectory,
    [Parameter(Mandatory)][string]$SharedRepositoryPath,
    [string[]]$AllowedRemote = @('https://github.com/tetsujisugimori-coder/LangBench-Live.git','https://github.com/tetsujisugimori-coder/LangBench-Live','git@github.com:tetsujisugimori-coder/LangBench-Live.git'),
    # Fixture-only preflight boundary; production workflow never supplies it.
    [switch]$TestPreflightOnly,
    [ValidateSet('generation')][string]$TestFailureStage
)
$ErrorActionPreference = 'Stop'
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'Never'
function Git([string]$Repository, [string[]]$Arguments, [int[]]$AllowedExitCodes = @(0)) {
    $oldEncoding = [Console]::OutputEncoding
    $oldAttributesNoSystem = $env:GIT_ATTR_NOSYSTEM
    try {
        [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
        $env:GIT_ATTR_NOSYSTEM = '1'
        $value = & git.exe -c core.quotepath=false -c core.hooksPath=NUL -c core.fsmonitor=false `
            -c core.attributesFile=NUL -c submodule.recurse=false -c fetch.recurseSubmodules=false `
            -c filter.lfs.clean= -c filter.lfs.smudge= -c filter.lfs.process= -c filter.lfs.required=false `
            -C $Repository @Arguments
        if ($LASTEXITCODE -notin $AllowedExitCodes) { throw "git failed: $($Arguments -join ' ')" }
    } finally {
        [Console]::OutputEncoding = $oldEncoding
        $env:GIT_ATTR_NOSYSTEM = $oldAttributesNoSystem
    }
    return $value
}
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) { throw 'validation output already exists' }
$execution = [IO.Path]::GetFullPath($ExecutionDirectory)
if (Test-Path -LiteralPath $execution) { throw 'independent execution directory already exists' }
if ((Git $sourceRoot @('rev-parse','HEAD')).Trim() -cne $TrustedSha) { throw 'runner source checkout differs from authorized SHA' }
$pathSeparators = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$shared = [IO.Path]::GetFullPath($SharedRepositoryPath).TrimEnd($pathSeparators)
if (-not (Test-Path -LiteralPath $shared -PathType Container)) { throw 'shared repository is absent' }
$topLevel = [IO.Path]::GetFullPath((Git $shared @('rev-parse','--show-toplevel')).Trim()).TrimEnd($pathSeparators)
if ($topLevel -ine $shared) { throw 'shared path is not its repository root' }
if ($AllowedRemote -inotcontains (Git $shared @('remote','get-url','origin')).Trim()) { throw 'shared repository origin is unexpected' }
# Refuse every effective content filter before status can inspect worktree files.
$filterKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($key in @(Git $shared @('config','--name-only','--get-regexp','^filter\..*\.(clean|smudge|process|required)$') @(0,1))) {
    [void]$filterKeys.Add([string]$key)
}
foreach ($key in $filterKeys) {
    $value = (Git $shared @('config','--get',$key)).Trim()
    $safe = if ($key.EndsWith('.required', [StringComparison]::OrdinalIgnoreCase)) { $value -ceq 'false' } else { $value -ceq '' }
    if (-not $safe) { throw "effective Git filter is refused: $key" }
}
$sourceCommon = (Git $sourceRoot @('rev-parse','--path-format=absolute','--git-common-dir')).Trim()
$sharedCommon = (Git $shared @('rev-parse','--path-format=absolute','--git-common-dir')).Trim()
if ([IO.Path]::GetFullPath($sourceCommon) -ieq [IO.Path]::GetFullPath($sharedCommon)) { throw 'runner source and user working copy share a Git common directory' }
$branch = (@(Git $shared @('symbolic-ref','--quiet','--short','HEAD') @(0,1)) -join '').Trim()
if ($branch -cne 'main') { throw 'shared repository is not on main' }
if ((Git $shared @('rev-parse','HEAD')).Trim() -cne $TrustedSha) { throw 'shared main is not the authorized SHA; use the official sync workflow' }
$remoteBefore = ((Git $shared @('ls-remote','origin','refs/heads/main')) -split '\s+')[0]
if ($remoteBefore -cne $TrustedSha) { throw 'remote main changed or could not be verified' }
if (@(Git $shared @('status','--porcelain','--untracked-files=no')).Count) { throw 'shared repository has tracked changes' }
foreach ($marker in @('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply')) {
    $path = (Git $shared @('rev-parse','--path-format=absolute','--git-path',$marker)).Trim()
    if (Test-Path -LiteralPath $path) { throw "shared Git operation in progress: $marker" }
}
$indexLock = (Git $shared @('rev-parse','--path-format=absolute','--git-path','index.lock')).Trim()
if (Test-Path -LiteralPath $indexLock) { throw 'shared Git index lock is present' }
$common = $sharedCommon
$sharedLock = $null
$measurementLock = $null
try {
    # This is the user working-copy operation lock. remeasure takes the runner
    # checkout's distinct operation lock, then run_all takes its measurement lock.
    $sharedLock = [IO.File]::Open((Join-Path $common 'langbench-operation.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $measurementLockPath = Join-Path $shared 'results/function_call_numeric_sum.lock'
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $measurementLockPath) -PathType Container)) { throw 'shared results directory is absent' }
    $measurementLock = [IO.File]::Open($measurementLockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    $branch = (@(Git $shared @('symbolic-ref','--quiet','--short','HEAD') @(0,1)) -join '').Trim()
    if ($branch -cne 'main' -or
        (Git $shared @('rev-parse','HEAD')).Trim() -cne $TrustedSha -or @(Git $shared @('status','--porcelain','--untracked-files=no')).Count) {
        throw 'shared working-copy preconditions changed while acquiring locks'
    }
    foreach ($marker in @('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply','index.lock')) {
        $path = (Git $shared @('rev-parse','--path-format=absolute','--git-path',$marker)).Trim()
        if (Test-Path -LiteralPath $path) { throw "shared Git state changed while acquiring locks: $marker" }
    }
    $untracked = @(Git $shared @('ls-files','--others','--exclude-standard'))
    $ignored = @(Git $shared @('ls-files','--others','--ignored','--exclude-standard'))
    # The actively-held measurement lock is operational state, not user data,
    # and cannot be hashed while opened with FileShare.None.
    $protected = @($untracked + $ignored | Where-Object { $_.Replace('\','/') -cne 'results/function_call_numeric_sum.lock' } | Sort-Object -Unique)
    $before = @{}
    foreach ($relative in $protected) {
        $path = Join-Path $shared $relative
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $item = Get-Item -LiteralPath $path -Force
            if ($item.LinkType) { throw "protected shared path is a link: $relative" }
            $before[$relative] = [ordered]@{ size=$item.Length;
                sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
        }
    }
    if ($TestPreflightOnly) {
        if ($env:LANGBENCH_TEST_PREFLIGHT -cne '1') { throw 'fixture-only preflight boundary is disabled' }
        foreach ($relative in $before.Keys) {
            $path = Join-Path $shared $relative
            if ((Get-Item -LiteralPath $path -Force).Length -ne $before[$relative].size -or
                (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $before[$relative].sha256) {
                throw "protected fixture file changed: $relative"
            }
        }
        Write-Host "status=preflight-valid protected_files=$($before.Count)"
        return
    }
    $id = "issue74-run$RunId-attempt$RunAttempt-$($TrustedSha.Substring(0,12))"
    $diagnostic = "results/diagnostics/$id"
    $attributeFiles = @(Git $sourceRoot @('ls-tree','-r','--name-only',$TrustedSha) | Where-Object { $_ -eq '.gitattributes' -or $_ -like '*/.gitattributes' })
    foreach ($attributeFile in $attributeFiles) {
        $attributes = @(Git $sourceRoot @('show',"${TrustedSha}:$attributeFile"))
        if (@($attributes | Where-Object { $_ -match '(?:^|\s)(?:-?filter|filter=)(?:\s|$|\S+)' }).Count) {
            throw "trusted checkout .gitattributes contains a filter attribute: $attributeFile"
        }
    }
    Git $sourceRoot @('clone','--no-local','--no-hardlinks','--no-checkout',$sourceRoot,$execution) | Out-Null
    Git $execution @('checkout','--detach',$TrustedSha) | Out-Null
    if ((Git $execution @('rev-parse','HEAD')).Trim() -cne $TrustedSha) { throw 'independent trusted checkout failed' }
    $executionCommon = (Git $execution @('rev-parse','--path-format=absolute','--git-common-dir')).Trim()
    if ([IO.Path]::GetFullPath($executionCommon) -ieq [IO.Path]::GetFullPath($sharedCommon)) { throw 'execution checkout shares the user Git common directory' }
    Push-Location $execution
    try {
        if ($TestFailureStage) {
            if ($env:LANGBENCH_HOSTED_FIXTURE -cne '1') { throw 'hosted failure fixture is disabled' }
            & pwsh -NoProfile -Command 'exit 23'
        } else {
            & pwsh -NoProfile -File ./tools/remeasure_function_call.ps1 -Count 1 -MeasurementOrder direct_first -SeriesId $id -OutputDirectory $diagnostic
        }
        if ($LASTEXITCODE -ne 0) { throw "Count=1 measurement failed with exit code $LASTEXITCODE" }
    }
    finally { Pop-Location }
    $record = Get-Content -LiteralPath (Join-Path $execution "$diagnostic/runs.json") -Raw | ConvertFrom-Json
    if ($record.successful_runs -ne 1 -or $record.requested_runs -ne 1 -or $record.mode -ne 'single_order') { throw 'Count=1 validation did not complete' }
    $archive = [string]$record.runs[0].archive_path
    & python -B (Join-Path $execution 'tools/show_archive_samples.py') --json --all-languages $archive | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'archive validation failed' }
    $identityPath = Join-Path $env:RUNNER_TEMP "$id-identity.json"
    if (Test-Path -LiteralPath $identityPath) { throw 'identity output already exists' }
    [ordered]@{ issue=74; run_id=$RunId; run_attempt=$RunAttempt; trusted_sha=$TrustedSha; sync_run_id=$SyncRunId;
        count=1; balanced_order=$false; measurement_order='direct_first'; protected_untracked_count=$untracked.Count;
        protected_ignored_count=$ignored.Count } | ConvertTo-Json | Set-Content -LiteralPath $identityPath -Encoding utf8
    & python -B (Join-Path $execution 'tools/build_measurement_validation_evidence.py') $archive $output --identity $identityPath
    if ($LASTEXITCODE -ne 0) { throw 'evidence construction failed' }
    & python -B (Join-Path $execution 'tools/check_function_call_artifact_safety.py') $output
    if ($LASTEXITCODE -ne 0) { throw 'artifact safety validation failed' }
    $branch = (@(Git $shared @('symbolic-ref','--quiet','--short','HEAD') @(0,1)) -join '').Trim()
    if ($branch -cne 'main' -or
        (Git $shared @('rev-parse','HEAD')).Trim() -cne $TrustedSha -or @(Git $shared @('status','--porcelain','--untracked-files=no')).Count) {
        throw 'shared working copy changed during validation'
    }
    foreach ($marker in @('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply','index.lock')) {
        $path = (Git $shared @('rev-parse','--path-format=absolute','--git-path',$marker)).Trim()
        if (Test-Path -LiteralPath $path) { throw "shared Git state changed during validation: $marker" }
    }
    foreach ($relative in $before.Keys) {
        $path = Join-Path $shared $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            (Get-Item -LiteralPath $path -Force).Length -ne $before[$relative].size -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $before[$relative].sha256) {
            throw "protected shared file changed: $relative"
        }
    }
    $remoteAfter = ((Git $shared @('ls-remote','origin','refs/heads/main')) -split '\s+')[0]
    if ($remoteAfter -cne $TrustedSha) { throw 'remote main changed during validation' }
} finally {
    if ($measurementLock) { $measurementLock.Dispose() }
    if ($sharedLock) { $sharedLock.Dispose() }
}
