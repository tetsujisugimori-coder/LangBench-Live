param(
    [Parameter(Mandatory)][string]$RepositoryPath,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$TargetSha,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$MergeSha
)
$ErrorActionPreference = 'Stop'
$expectedRemotes = @('https://github.com/tetsujisugimori-coder/LangBench-Live.git','https://github.com/tetsujisugimori-coder/LangBench-Live','git@github.com:tetsujisugimori-coder/LangBench-Live.git')
function Git { $value = & git -c core.hooksPath=NUL -c filter.lfs.smudge= -c filter.lfs.required=false @args; if ($LASTEXITCODE) { throw "git failed: $($args -join ' ')" }; $value }

$root = [IO.Path]::GetFullPath($RepositoryPath).TrimEnd('\')
if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw 'Repository folder does not exist.' }
Set-Location -LiteralPath $root
if ([IO.Path]::GetFullPath((Git rev-parse --show-toplevel)).TrimEnd('\') -ine $root) { throw 'Configured path is not the repository root.' }
if ($expectedRemotes -inotcontains (Git remote get-url origin)) { throw 'Unexpected origin.' }
if (@(Git status --porcelain --untracked-files=no).Count) { throw 'Tracked changes are present.' }
foreach ($marker in @('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply')) {
    if (Test-Path -LiteralPath (Join-Path (Git rev-parse --git-path $marker) '')) { throw "Git operation in progress: $marker" }
}
$branch = (Git symbolic-ref --short HEAD)
if ($branch -ne 'main') { throw "Automatic switching from branch '$branch' is refused." }

$lockPath = Join-Path (Git rev-parse --git-common-dir) 'langbench-operation.lock'
$lock = $null
try {
    $lock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    $protected = @(& git ls-files --others --ignored --exclude-standard -z) -join '' -split "`0" | Where-Object { $_ }
    $before = @{}
    foreach ($relative in $protected) {
        $path = Join-Path $root $relative
        if ((Get-Item -LiteralPath $path).LinkType) { throw "Link cannot be protected safely: $relative" }
        if (Test-Path -LiteralPath $path -PathType Leaf) { $before[$relative.ToLowerInvariant()] = @{ path=$relative; size=(Get-Item $path).Length; hash=(Get-FileHash $path -Algorithm SHA256).Hash } }
    }
    Git fetch --no-tags origin "+refs/heads/main:refs/remotes/origin/main" | Out-Null
    if ((Git rev-parse origin/main) -ne $TargetSha) { throw 'Fetched main differs from the validated event SHA.' }
    & git merge-base --is-ancestor HEAD $TargetSha; if ($LASTEXITCODE) { throw 'Local main cannot fast-forward.' }
    & git merge-base --is-ancestor $MergeSha $TargetSha; if ($LASTEXITCODE) { throw 'Validated merge result is not in target history.' }
    $targetFiles = @(Git ls-tree -r --name-only $TargetSha)
    foreach ($name in $targetFiles) { if ($before.ContainsKey($name.ToLowerInvariant())) { throw "Protected path conflicts with target: $name" } }
    Git merge --ff-only $TargetSha | Out-Null
    if ((Git rev-parse HEAD) -ne $TargetSha) { throw 'Final HEAD mismatch.' }
    foreach ($item in $before.Values) {
        $path = Join-Path $root $item.path
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item $path).Length -ne $item.size -or (Get-FileHash $path -Algorithm SHA256).Hash -ne $item.hash) { throw "Protected file changed: $($item.path)" }
    }
    Write-Host "status=success before/after=$TargetSha protected_files=$($before.Count)"
} finally { if ($lock) { $lock.Dispose() } }
