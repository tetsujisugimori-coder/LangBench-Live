$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $root 'tools/sync_local_main.ps1'
$sandbox = Join-Path ([IO.Path]::GetTempPath()) "langbench-sync-test-$([guid]::NewGuid().ToString('N'))"
$passed = 0

function G([string]$Directory, [Parameter(ValueFromRemainingArguments)]$Arguments) {
    & git -C $Directory @Arguments | Out-Null
    if ($LASTEXITCODE) { throw "fixture git failed: $($Arguments -join ' ')" }
}
function New-Fixture {
    $folder = Join-Path $sandbox ([guid]::NewGuid().ToString('N')); $bare = Join-Path $folder 'remote.git'; $seed = Join-Path $folder 'seed'; $local = Join-Path $folder 'local'
    New-Item -ItemType Directory -Path $folder | Out-Null; & git init --bare $bare | Out-Null; & git init -b main $seed | Out-Null
    G $seed config user.email test@example.invalid; G $seed config user.name test
    Set-Content (Join-Path $seed 'base.txt') base; G $seed add base.txt; G $seed commit -m base; G $seed remote add origin $bare; G $seed push -u origin main
    G $bare symbolic-ref HEAD refs/heads/main
    & git clone $bare $local | Out-Null
    G $seed switch -c issue-66; Set-Content (Join-Path $seed 'feature.txt') feature; G $seed add feature.txt; G $seed commit -m feature
    $prHead = (& git -C $seed rev-parse HEAD).Trim(); G $seed push origin issue-66; G $seed switch main; G $seed merge --no-ff issue-66 -m merge; G $seed push origin main
    $target = (& git -C $seed rev-parse HEAD).Trim()
    return @{ Folder=$folder; Bare=$bare; Seed=$seed; Local=$local; PrHead=$prHead; Target=$target }
}
function Invoke-Sync($fixture, [switch]$Fail) {
    $errorSeen = $false
    try { & $script -RepositoryPath $fixture.Local -TargetSha $fixture.Target -MergeSha $fixture.Target -PullRequestHeadSha $fixture.PrHead -PullRequestNumber 67 -AllowedRemote $fixture.Bare }
    catch { $errorSeen = $true }
    if ($Fail -ne $errorSeen) { throw "Expected failure=$Fail, actual failure=$errorSeen" }
    $script:passed++
}
function Test-Failure([scriptblock]$Arrange) { $f = New-Fixture; & $Arrange $f; Invoke-Sync $f -Fail }

try {
    New-Item -ItemType Directory -Path $sandbox | Out-Null
    $f = New-Fixture; Invoke-Sync $f; if ((& git -C $f.Local rev-parse HEAD).Trim() -ne $f.Target) { throw 'fast-forward failed' }
    Invoke-Sync $f # update unnecessary

    Test-Failure { param($f) Set-Content (Join-Path $f.Local tracked.txt) x; G $f.Local add tracked.txt }
    Test-Failure { param($f) Set-Content (Join-Path $f.Local base.txt) modified }
    $f = New-Fixture; Set-Content (Join-Path $f.Local keep.txt) keep; Invoke-Sync $f; if ((Get-Content (Join-Path $f.Local keep.txt)) -ne 'keep') { throw 'untracked changed' }
    $f = New-Fixture; Add-Content (Join-Path $f.Local .git/info/exclude) "`nignored.txt"; Set-Content (Join-Path $f.Local ignored.txt) keep; Invoke-Sync $f; if ((Get-Content (Join-Path $f.Local ignored.txt)) -ne 'keep') { throw 'ignored changed' }

    foreach ($name in @('feature.txt','FEATURE.TXT')) {
        $collisionName = $name
        $arrange = { param($f) Set-Content (Join-Path $f.Local $collisionName) protected }.GetNewClosure()
        Test-Failure $arrange
    }
    Test-Failure { param($f) New-Item -ItemType Directory (Join-Path $f.Local feature.txt) | Out-Null; Set-Content (Join-Path $f.Local feature.txt/child) protected }
    Test-Failure { param($f) G $f.Local switch -c unrelated; Set-Content (Join-Path $f.Local other.txt) other; G $f.Local add other.txt; G $f.Local -c user.email=x@y -c user.name=x commit -m other }

    $f = New-Fixture; G $f.Local fetch origin issue-66:issue-66; G $f.Local switch issue-66; Invoke-Sync $f
    Test-Failure { param($f) G $f.Local checkout --detach }
    Test-Failure { param($f) Set-Content (Join-Path $f.Local .git/MERGE_HEAD) ('0' * 40) }
    Test-Failure { param($f) G $f.Local remote set-url origin (Join-Path $f.Folder wrong.git) }
    Test-Failure { param($f) G $f.Local switch -c temporary; G $f.Local branch -D main }
    Test-Failure { param($f) Set-Content (Join-Path $f.Local local.txt) x; G $f.Local add local.txt; G $f.Local -c user.email=x@y -c user.name=x commit -m local-ahead }
    Test-Failure { param($f) G $f.Local fetch origin issue-66:issue-66; G $f.Local switch issue-66; G $f.Local worktree add (Join-Path $f.Folder main-worktree) main }

    $f = New-Fixture; $lock = [IO.File]::Open((Join-Path $f.Local '.git/langbench-operation.lock'),'OpenOrCreate','ReadWrite','None')
    try { Invoke-Sync $f -Fail } finally { $lock.Dispose() }
    Write-Host "sync_local_main tests passed: $passed"
} finally { Remove-Item -LiteralPath $sandbox -Recurse -Force -ErrorAction SilentlyContinue }
