param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$TrustedSha,
    [Parameter(Mandatory)][ValidateRange(1, [long]::MaxValue)][long]$RunId,
    [Parameter(Mandatory)][ValidateRange(1, [int]::MaxValue)][int]$RunAttempt,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [Parameter(Mandatory)][string]$SharedRepositoryPath
)
$ErrorActionPreference = 'Stop'
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'Never'
function Git([string]$Repository, [string[]]$Arguments) {
    $value = & git.exe -c core.quotepath=false -c core.hooksPath=NUL -c core.fsmonitor=false `
        -c core.attributesFile=NUL -c submodule.recurse=false -c fetch.recurseSubmodules=false `
        -c filter.lfs.clean= -c filter.lfs.smudge= -c filter.lfs.process= -c filter.lfs.required=false `
        -C $Repository @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git failed: $($Arguments -join ' ')" }
    return $value
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) { throw 'validation output already exists' }
if ((Git $root @('rev-parse','HEAD')).Trim() -cne $TrustedSha) { throw 'runner checkout differs from authorized SHA' }
$shared = [IO.Path]::GetFullPath($SharedRepositoryPath).TrimEnd('\')
if (-not (Test-Path -LiteralPath $shared -PathType Container)) { throw 'shared repository is absent' }
$allowed = @('https://github.com/tetsujisugimori-coder/LangBench-Live.git','https://github.com/tetsujisugimori-coder/LangBench-Live','git@github.com:tetsujisugimori-coder/LangBench-Live.git')
if ((Git $shared @('rev-parse','--show-toplevel')).Trim().TrimEnd('\') -ine $shared) { throw 'shared path is not its repository root' }
if ($allowed -inotcontains (Git $shared @('remote','get-url','origin')).Trim()) { throw 'shared repository origin is unexpected' }
if ((Git $shared @('symbolic-ref','--quiet','--short','HEAD')).Trim() -cne 'main') { throw 'shared repository is not on main' }
if ((Git $shared @('rev-parse','HEAD')).Trim() -cne $TrustedSha) { throw 'shared main is not the authorized SHA; use the official sync workflow' }
$remoteBefore = ((Git $shared @('ls-remote','origin','refs/heads/main')) -split '\s+')[0]
if ($remoteBefore -cne $TrustedSha) { throw 'remote main changed or could not be verified' }
if (@(Git $shared @('status','--porcelain','--untracked-files=no')).Count) { throw 'shared repository has tracked changes' }
foreach ($marker in @('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply')) {
    $path = (Git $shared @('rev-parse','--git-path',$marker)).Trim()
    if (Test-Path -LiteralPath $path) { throw "shared Git operation in progress: $marker" }
}
$common = (Git $shared @('rev-parse','--path-format=absolute','--git-common-dir')).Trim()
$sharedLock = $null
try {
    # This is the user working-copy operation lock. remeasure takes the runner
    # checkout's distinct operation lock, then run_all takes its measurement lock.
    $sharedLock = [IO.File]::Open((Join-Path $common 'langbench-operation.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $untracked = @(Git $shared @('ls-files','--others','--exclude-standard'))
    $ignored = @(Git $shared @('ls-files','--others','--ignored','--exclude-standard'))
    $protected = @($untracked + $ignored | Sort-Object -Unique)
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
    $id = "issue74-run$RunId-attempt$RunAttempt-$($TrustedSha.Substring(0,12))"
    $diagnostic = "results/diagnostics/$id"
    Push-Location $root
    try { ./tools/remeasure_function_call.ps1 -Count 1 -MeasurementOrder direct_first -SeriesId $id -OutputDirectory $diagnostic }
    finally { Pop-Location }
    $record = Get-Content -LiteralPath (Join-Path $root "$diagnostic/runs.json") -Raw | ConvertFrom-Json
    if ($record.successful_runs -ne 1 -or $record.requested_runs -ne 1 -or $record.mode -ne 'single_order') { throw 'Count=1 validation did not complete' }
    $archive = [string]$record.runs[0].archive_path
    & python -B (Join-Path $root 'tools/show_archive_samples.py') --json --all-languages $archive | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'archive validation failed' }
    $identityPath = Join-Path $env:RUNNER_TEMP "$id-identity.json"
    [ordered]@{ issue=74; run_id=$RunId; run_attempt=$RunAttempt; trusted_sha=$TrustedSha; sync_required=$false;
        count=1; balanced_order=$false; measurement_order='direct_first'; protected_untracked_count=$untracked.Count;
        protected_ignored_count=$ignored.Count } | ConvertTo-Json | Set-Content -LiteralPath $identityPath -Encoding utf8
    & python -B (Join-Path $root 'tools/build_measurement_validation_evidence.py') $archive $output --identity $identityPath
    if ($LASTEXITCODE -ne 0) { throw 'evidence construction failed' }
    if ((Git $shared @('rev-parse','HEAD')).Trim() -cne $TrustedSha -or @(Git $shared @('status','--porcelain','--untracked-files=no')).Count) {
        throw 'shared working copy changed during validation'
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
    if ($sharedLock) { $sharedLock.Dispose() }
}
