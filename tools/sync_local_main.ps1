param(
    [Parameter(Mandatory)][string]$RepositoryPath,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$TargetSha,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$MergeSha,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$PullRequestHeadSha,
    [Parameter(Mandatory)][ValidateRange(1, [int]::MaxValue)][int]$PullRequestNumber,
    [string[]]$AllowedRemote = @('https://github.com/tetsujisugimori-coder/LangBench-Live.git','https://github.com/tetsujisugimori-coder/LangBench-Live','git@github.com:tetsujisugimori-coder/LangBench-Live.git')
)
$ErrorActionPreference = 'Stop'
function Git { $value = & git -c core.hooksPath=NUL -c core.fsmonitor=false -c filter.lfs.smudge= -c filter.lfs.required=false @args; if ($LASTEXITCODE) { throw "git failed: $($args -join ' ')" }; $value }
function Git-One { $lines = @(Git @args); if ($lines.Count -ne 1) { throw "Expected one line from git $($args -join ' ')" }; return [string]$lines[0] }
function Normalize([string]$Path) { $Path.Replace('\','/').TrimStart([char[]]'./').TrimEnd('/').ToLowerInvariant() }

$root = [IO.Path]::GetFullPath($RepositoryPath).TrimEnd('\')
if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw 'Repository folder does not exist.' }
Push-Location -LiteralPath $root
try {
if ([IO.Path]::GetFullPath((Git-One rev-parse --show-toplevel)).TrimEnd('\') -ine $root) { throw 'Configured path is not the repository root.' }
if ($AllowedRemote -inotcontains (Git-One remote get-url origin)) { throw 'Unexpected origin.' }
$localFilters = @(& git -c core.fsmonitor=false config --local --get-regexp '^filter\..*\.(clean|smudge|process|required)$' 2>$null)
if ($LASTEXITCODE -notin @(0, 1)) { throw 'Cannot inspect repository-local filters.' }
if ($localFilters.Count) { throw 'Repository-local Git filters are refused during automatic sync.' }
if (@(Git status --porcelain --untracked-files=no).Count) { throw 'Tracked changes are present.' }
foreach ($marker in @('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply')) {
    if (Test-Path -LiteralPath (Git-One rev-parse --git-path $marker)) { throw "Git operation in progress: $marker" }
}
& git show-ref --verify --quiet refs/heads/main
if ($LASTEXITCODE -ne 0) { throw 'Local main does not exist.' }
$branchOutput = @(& git symbolic-ref --quiet --short HEAD)
if ($LASTEXITCODE -ne 0 -or $branchOutput.Count -ne 1) { throw 'Detached HEAD is refused.' }
$branch = [string]$branchOutput[0]
$headBefore = Git-One rev-parse HEAD
if ($branch -ne 'main' -and $headBefore -ne $PullRequestHeadSha) {
    throw "Automatic switching from unrelated branch '$branch' is refused."
}
$mainUsers = @(Git worktree list --porcelain | Where-Object { $_ -eq 'branch refs/heads/main' })
if ($branch -ne 'main' -and $mainUsers.Count) { throw 'main is checked out by another worktree.' }

$lockPath = Join-Path (Git-One rev-parse --git-common-dir) 'langbench-operation.lock'
$lock = $null
try {
    $lock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    $untracked = ((@(& git ls-files --others --exclude-standard -z) -join '') -split "`0") | Where-Object { $_ }
    if ($LASTEXITCODE) { throw 'Cannot enumerate untracked files.' }
    $ignored = ((@(& git ls-files --others --ignored --exclude-standard -z) -join '') -split "`0") | Where-Object { $_ }
    if ($LASTEXITCODE) { throw 'Cannot enumerate ignored files.' }
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
    Git fetch --no-tags origin "+refs/heads/main:refs/remotes/origin/main" | Out-Null
    if ((Git-One rev-parse origin/main) -ne $TargetSha) { throw 'Fetched main differs from the validated event SHA.' }
    & git merge-base --is-ancestor refs/heads/main $TargetSha; if ($LASTEXITCODE) { throw 'Local main cannot fast-forward.' }
    & git merge-base --is-ancestor $MergeSha $TargetSha; if ($LASTEXITCODE) { throw 'Validated merge result is not in target history.' }
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
    Write-Host "status=success pr=$PullRequestNumber pr_head=$PullRequestHeadSha merge=$MergeSha target=$TargetSha before=$headBefore after=$TargetSha protected_files=$($before.Count)"
} finally { if ($lock) { $lock.Dispose() } }
} finally { Pop-Location }
