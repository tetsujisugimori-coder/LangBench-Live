param(
    [Parameter(Mandatory)][string]$RepositoryPath,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$TargetSha,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$MergeSha,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$PullRequestHeadSha,
    [Parameter(Mandatory)][ValidateRange(1, [int]::MaxValue)][int]$PullRequestNumber,
    [string[]]$AllowedRemote = @('https://github.com/tetsujisugimori-coder/LangBench-Live.git','https://github.com/tetsujisugimori-coder/LangBench-Live','git@github.com:tetsujisugimori-coder/LangBench-Live.git'),
    # Optional public safety evidence; production supplies a fresh RUNNER_TEMP path.
    [string]$ReportPath,
    # Test-only fixed path markers; never supplied by the production workflow.
    [string]$TestPhaseDirectory
)
$ErrorActionPreference = 'Stop'
function Invoke-HardenedGit([string[]]$Arguments, [int[]]$AllowedExitCodes = @(0)) {
    # git.exe avoids PowerShell resolving 'git' back to the Git function.
    # Git emits UTF-8 paths even when a Windows caller uses CP932. Decode them
    # explicitly and restore the caller's console encoding after every command.
    $oldOutputEncoding = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
        $value = & git.exe -c core.quotepath=false -c core.hooksPath=NUL -c core.fsmonitor=false -c core.attributesFile=NUL -c submodule.recurse=false -c fetch.recurseSubmodules=false -c filter.lfs.clean= -c filter.lfs.smudge= -c filter.lfs.process= -c filter.lfs.required=false @Arguments
        if ($LASTEXITCODE -notin $AllowedExitCodes) { throw "git failed: $($Arguments -join ' ')" }
    } finally { [Console]::OutputEncoding = $oldOutputEncoding }
    $value
}
function Git { Invoke-HardenedGit -Arguments $args }
function Git-One { $lines = @(Git @args); if ($lines.Count -ne 1) { throw "Expected one line from git $($args -join ' ')" }; return [string]$lines[0] }
function Normalize([string]$Path) { $Path.Replace('\','/').TrimStart([char[]]'./').TrimEnd('/').ToLowerInvariant() }

$root = [IO.Path]::GetFullPath($RepositoryPath).TrimEnd('\')
if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw 'Repository folder does not exist.' }
Push-Location -LiteralPath $root
$oldAttributesNoSystem = $env:GIT_ATTR_NOSYSTEM
$env:GIT_ATTR_NOSYSTEM = '1'
try {
if ([IO.Path]::GetFullPath((Git-One rev-parse --show-toplevel)).TrimEnd('\') -ine $root) { throw 'Configured path is not the repository root.' }
if ($AllowedRemote -inotcontains (Git-One remote get-url origin)) { throw 'Unexpected origin.' }
# Enumerate all scopes, but judge each key's last/effective value under the same
# command-scope hardening as status/fetch/merge. A shadowed definition cannot
# execute. Filter subsection names are case-sensitive, so never collapse LFS/lfs.
$filterKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($key in @(Git config --name-only --get-regexp '^filter\..*\.(clean|smudge|process|required)$')) {
    [void]$filterKeys.Add([string]$key)
}
foreach ($key in $filterKeys) {
    if ($key.EndsWith('.required', [StringComparison]::OrdinalIgnoreCase)) {
        $effectiveValue = Git-One config --type=bool --get $key
        $safe = $effectiveValue -ceq 'false'
    } else {
        $effectiveValue = Git-One config --get $key
        $safe = $effectiveValue -ceq ''
    }
    if (-not $safe) { throw "Effective Git filters are refused during automatic sync: $key" }
}
if (@(Git status --porcelain --untracked-files=no).Count) { throw 'Tracked changes are present.' }
foreach ($marker in @('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply')) {
    if (Test-Path -LiteralPath (Git-One rev-parse --git-path $marker)) { throw "Git operation in progress: $marker" }
}
Git show-ref --verify --quiet refs/heads/main | Out-Null
$branchOutput = @(Git symbolic-ref --quiet --short HEAD)
if ($branchOutput.Count -ne 1) { throw 'Detached HEAD is refused.' }
$branch = [string]$branchOutput[0]
$headBefore = Git-One rev-parse HEAD
if ($branch -ne 'main' -and $headBefore -ne $PullRequestHeadSha) {
    throw "Automatic switching from unrelated branch '$branch' is refused."
}
$mainUsers = @(Git worktree list --porcelain | Where-Object { $_ -eq 'branch refs/heads/main' })
if ($branch -ne 'main' -and $mainUsers.Count) { throw 'main is checked out by another worktree.' }

# File.Open resolves relative paths against the process directory, which
# PowerShell Push-Location does not change. Lock the absolute common directory.
$lockPath = Join-Path (Git-One rev-parse --path-format=absolute --git-common-dir) 'langbench-operation.lock'
$lock = $null
try {
    $lock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    $untracked = ((@(Git ls-files --others --exclude-standard -z) -join '') -split "`0") | Where-Object { $_ }
    $ignored = ((@(Git ls-files --others --ignored --exclude-standard -z) -join '') -split "`0") | Where-Object { $_ }
    $protected = @($untracked + $ignored | Sort-Object -Unique)
    $before = @{}
    foreach ($relative in $protected) {
        $path = Join-Path $root $relative; $item = Get-Item -LiteralPath $path -Force
        if ($item.LinkType -or -not $item.PSIsContainer -and -not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Protected path cannot be verified: $relative" }
        if (-not $item.PSIsContainer) {
            $key = Normalize $relative
            if ($before.ContainsKey($key)) { throw "Protected paths collide under Windows case rules: $relative" }
            $before[$key] = @{ path=$relative; size=$item.Length; hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
        }
    }
    Git fetch --no-tags --no-recurse-submodules origin "+refs/heads/main:refs/remotes/origin/main" | Out-Null
    if ((Git-One rev-parse origin/main) -ne $TargetSha) { throw 'Fetched main differs from the validated event SHA.' }
    Write-Host "phase=target-validated sha=$TargetSha"
    if ($TestPhaseDirectory) {
        $phaseDirectory = [IO.Path]::GetFullPath($TestPhaseDirectory)
        [IO.Directory]::CreateDirectory($phaseDirectory) | Out-Null
        Set-Content -LiteralPath (Join-Path $phaseDirectory 'target-validated') -Value $TargetSha -Encoding ascii
        $deadline = [DateTime]::UtcNow.AddSeconds(30)
        while (-not (Test-Path -LiteralPath (Join-Path $phaseDirectory 'continue'))) {
            if ([DateTime]::UtcNow -ge $deadline) { throw 'Timed out waiting at the fixed synchronization test phase.' }
            Start-Sleep -Milliseconds 50
        }
    }
    Git merge-base --is-ancestor refs/heads/main $TargetSha | Out-Null
    Git merge-base --is-ancestor $MergeSha $TargetSha | Out-Null
    $gitlinks = @(Git ls-tree -r $TargetSha | Where-Object { $_ -match '^160000\s' })
    if ($gitlinks.Count) { throw 'Target contains a gitlink; automatic sync refuses submodules.' }
    $attributeFiles = @(Git ls-tree -r --name-only $TargetSha | Where-Object { $_ -eq '.gitattributes' -or $_ -like '*/.gitattributes' })
    foreach ($attributeFile in $attributeFiles) {
        $attributes = @(Git show "${TargetSha}:$attributeFile")
        if (@($attributes | Where-Object { $_ -match '(?:^|\s)(?:-?filter|filter=)(?:\s|$|\S+)' }).Count) {
            throw "Target .gitattributes contains a filter attribute: $attributeFile"
        }
    }
    $targetFiles = @(Git ls-tree -r --name-only $TargetSha | ForEach-Object { Normalize $_ })
    foreach ($protectedName in $before.Keys) {
        foreach ($targetName in $targetFiles) {
            if ($protectedName -eq $targetName -or $protectedName.StartsWith($targetName + '/') -or $targetName.StartsWith($protectedName + '/')) {
                throw "Protected path conflicts with target: $($before[$protectedName].path)"
            }
        }
    }
    if ($branch -ne 'main') { Git switch main | Out-Null }
    Git merge --ff-only $TargetSha | Out-Null
    if ((Git-One rev-parse HEAD) -ne $TargetSha -or (Git-One symbolic-ref --short HEAD) -ne 'main') { throw 'Final branch or HEAD mismatch.' }
    foreach ($item in $before.Values) {
        $path = Join-Path $root $item.path
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -ne $item.size -or
                (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $item.hash) { throw "Protected file changed: $($item.path)" }
    }
    Git fetch --no-tags --no-recurse-submodules origin "+refs/heads/main:refs/remotes/origin/main" | Out-Null
    $latestRemote = Git-One rev-parse origin/main
    if ($latestRemote -ne $TargetSha) {
        throw "main advanced during sync: validated=$TargetSha latest=$latestRemote"
    }
    Write-Host "status=success pr=$PullRequestNumber pr_head=$PullRequestHeadSha merge=$MergeSha target=$TargetSha before=$headBefore after=$TargetSha protected_files=$($before.Count)"
    if ($ReportPath) {
        if (Test-Path -LiteralPath $ReportPath) { throw 'Sync report path already exists.' }
        if ($env:GITHUB_RUN_ID -notmatch '^\d+$' -or $env:GITHUB_RUN_ATTEMPT -notmatch '^\d+$') { throw 'Sync report requires Actions run identity.' }
        $report = [ordered]@{
            schema_version = 1; repository = 'tetsujisugimori-coder/LangBench-Live'
            pr = $PullRequestNumber; pr_head_sha = $PullRequestHeadSha
            merge_sha = $MergeSha; target_sha = $TargetSha
            before_sha = $headBefore; after_sha = $TargetSha
            protected_files = $before.Count; protected_preserved = $true
            run_id = [string]$env:GITHUB_RUN_ID; run_attempt = [int]$env:GITHUB_RUN_ATTEMPT
            status = 'success'
        }
        [IO.File]::WriteAllText([IO.Path]::GetFullPath($ReportPath), ($report | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    }
} finally { if ($lock) { $lock.Dispose() } }
} finally { $env:GIT_ATTR_NOSYSTEM = $oldAttributesNoSystem; Pop-Location }
