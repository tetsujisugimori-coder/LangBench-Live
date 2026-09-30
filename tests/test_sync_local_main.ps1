$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $root 'tools/sync_local_main.ps1'
$sandbox = Join-Path ([IO.Path]::GetTempPath()) "langbench-sync-test-$([guid]::NewGuid().ToString('N'))"
$originalLocation = (Get-Location).Path
$passed = 0

function G([string]$Directory, [Parameter(ValueFromRemainingArguments)]$Arguments) {
    & git -C $Directory @Arguments | Out-Null
    if ($LASTEXITCODE) { throw "fixture git failed: $($Arguments -join ' ')" }
}
function New-Fixture([string]$Name = $([guid]::NewGuid().ToString('N'))) {
    $folder = Join-Path $sandbox $Name; $bare = Join-Path $folder 'remote.git'; $seed = Join-Path $folder 'seed'; $local = Join-Path $folder 'local'
    New-Item -ItemType Directory -Path $folder | Out-Null; & git init --bare $bare | Out-Null; & git init -b main $seed | Out-Null
    G $seed config user.email test@example.invalid; G $seed config user.name test
    Set-Content (Join-Path $seed 'base.txt') base; G $seed add base.txt; G $seed commit -m base; G $seed remote add origin $bare; G $seed push -u origin main
    G $bare symbolic-ref HEAD refs/heads/main; & git clone $bare $local | Out-Null
    G $seed switch -c issue-66; Set-Content (Join-Path $seed 'feature.txt') feature; G $seed add feature.txt; G $seed commit -m feature
    $prHead = (& git -C $seed rev-parse HEAD).Trim(); G $seed push origin issue-66; G $seed switch main; G $seed merge --no-ff issue-66 -m merge; G $seed push origin main
    return @{ Folder=$folder; Bare=$bare; Seed=$seed; Local=$local; PrHead=$prHead; Target=(& git -C $seed rev-parse HEAD).Trim() }
}
function Invoke-Sync($Fixture, [switch]$Fail) {
    $before = (Get-Location).Path; $errorSeen = $false
    try { & $script -RepositoryPath $Fixture.Local -TargetSha $Fixture.Target -MergeSha $Fixture.Target -PullRequestHeadSha $Fixture.PrHead -PullRequestNumber 67 -AllowedRemote $Fixture.Bare }
    catch { $errorSeen = $true; if (-not $Fail) { throw } }
    if ((Get-Location).Path -ne $before) { throw 'sync script did not restore the caller location' }
    if ($Fail -ne $errorSeen) { throw "Expected failure=$Fail, actual failure=$errorSeen" }
}
function Run-Case([string]$Name, [scriptblock]$Body) {
    Write-Host "CASE START: $Name"
    try { & $Body; $script:passed++; Write-Host "CASE PASS: $Name" }
    catch { Write-Host "CASE FAIL: $Name -- $($_.Exception.Message)"; throw }
}
function Failure-Case([string]$Name, [scriptblock]$Arrange) {
    $body = { $f = New-Fixture; & $Arrange $f; Invoke-Sync $f -Fail }.GetNewClosure()
    Run-Case $Name $body
}

try {
    New-Item -ItemType Directory -Path $sandbox | Out-Null
    Run-Case 'normal fast-forward and update unnecessary' { $f = New-Fixture; Invoke-Sync $f; Invoke-Sync $f; if ((& git -C $f.Local rev-parse HEAD).Trim() -ne $f.Target) { throw 'fast-forward failed' } }
    Run-Case 'Japanese and spaces repository path' { $f = New-Fixture '日本語 と spaces'; Invoke-Sync $f }
    Failure-Case 'staged tracked change' { param($f) Set-Content (Join-Path $f.Local tracked.txt) x; G $f.Local add tracked.txt }
    Failure-Case 'unstaged tracked change' { param($f) Set-Content (Join-Path $f.Local base.txt) modified }
    Run-Case 'untracked preserved' { $f = New-Fixture; Set-Content (Join-Path $f.Local keep.txt) keep; Invoke-Sync $f; if ((Get-Content (Join-Path $f.Local keep.txt)) -ne 'keep') { throw 'untracked changed' } }
    Run-Case 'ignored preserved' { $f = New-Fixture; Add-Content (Join-Path $f.Local .git/info/exclude) "`nignored.txt"; Set-Content (Join-Path $f.Local ignored.txt) keep; Invoke-Sync $f; if ((Get-Content (Join-Path $f.Local ignored.txt)) -ne 'keep') { throw 'ignored changed' } }
    foreach ($name in @('feature.txt','FEATURE.TXT')) {
        $collision=$name; $arrange={ param($f) Set-Content (Join-Path $f.Local $collision) protected }.GetNewClosure()
        Failure-Case "collision $name" $arrange
    }
    Failure-Case 'file directory collision' { param($f) New-Item -ItemType Directory (Join-Path $f.Local feature.txt) | Out-Null; Set-Content (Join-Path $f.Local feature.txt/child) protected }
    Failure-Case 'unrelated branch' { param($f) G $f.Local switch -c unrelated; Set-Content (Join-Path $f.Local other.txt) other; G $f.Local add other.txt; G $f.Local -c user.email=x@y -c user.name=x commit -m other }
    Run-Case 'safe PR branch switch' { $f=New-Fixture; G $f.Local fetch origin issue-66:issue-66; G $f.Local switch issue-66; Invoke-Sync $f }
    Failure-Case 'detached HEAD' { param($f) G $f.Local checkout --detach }
    Failure-Case 'Git operation in progress' { param($f) Set-Content (Join-Path $f.Local .git/MERGE_HEAD) ('0' * 40) }
    Failure-Case 'origin mismatch' { param($f) G $f.Local remote set-url origin (Join-Path $f.Folder wrong.git) }
    Failure-Case 'main absent' { param($f) G $f.Local switch -c temporary; G $f.Local branch -D main }
    Failure-Case 'diverged local main' { param($f) Set-Content (Join-Path $f.Local local.txt) x; G $f.Local add local.txt; G $f.Local -c user.email=x@y -c user.name=x commit -m local-ahead }
    Failure-Case 'main used by another worktree' { param($f) G $f.Local fetch origin issue-66:issue-66; G $f.Local switch issue-66; G $f.Local worktree add (Join-Path $f.Folder main-worktree) main }
    Failure-Case 'remote retrieval failure' { param($f) Remove-Item -LiteralPath $f.Bare -Recurse -Force }
    Failure-Case 'origin main advanced after validation' { param($f) Set-Content (Join-Path $f.Seed advanced.txt) x; G $f.Seed add advanced.txt; G $f.Seed commit -m advanced; G $f.Seed push origin main }
    Run-Case 'hooks and fsmonitor suppressed' {
        $f=New-Fixture; $sentinel=Join-Path $f.Folder sentinel; $hook=Join-Path $f.Local .git/hooks/post-merge
        Set-Content $hook "#!/bin/sh`necho hook > '$($sentinel.Replace('\','/'))'"; G $f.Local config core.fsmonitor "echo fsmonitor > '$($sentinel.Replace('\','/'))'"
        Invoke-Sync $f; if (Test-Path $sentinel) { throw 'hook or fsmonitor unexpectedly executed' }
    }
    Failure-Case 'repository-local filter refused' { param($f) G $f.Local config filter.unsafe.smudge 'unsafe-command' }
    Run-Case 'lock conflict' { $f=New-Fixture; $lock=[IO.File]::Open((Join-Path $f.Local '.git/langbench-operation.lock'),'OpenOrCreate','ReadWrite','None'); try { Invoke-Sync $f -Fail } finally { $lock.Dispose() } }
    Write-Host "sync_local_main tests passed: $passed"
} finally {
    Set-Location -LiteralPath $originalLocation
    Remove-Item -LiteralPath $sandbox -Recurse -Force -ErrorAction SilentlyContinue
}
