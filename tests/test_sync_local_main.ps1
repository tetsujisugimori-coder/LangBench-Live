param([string]$Case)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $root 'tools/sync_local_main.ps1'
$sandbox = Join-Path ([IO.Path]::GetTempPath()) "langbench-sync-test-$([guid]::NewGuid().ToString('N'))"
$originalLocation = (Get-Location).Path
$passed = 0
$caseTimes = @{}
$suiteWatch = [Diagnostics.Stopwatch]::StartNew()

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
    if ($Case -and $Case -ne $Name) { return }
    $watch=[Diagnostics.Stopwatch]::StartNew(); Write-Host "CASE START: $Name at=$([DateTime]::UtcNow.ToString('o'))"
    try { & $Body; $script:passed++; $watch.Stop(); $script:caseTimes[$Name]=$watch.Elapsed.TotalSeconds; Write-Host ("CASE PASS: {0} elapsed={1:N2}s ended={2}" -f $Name,$watch.Elapsed.TotalSeconds,[DateTime]::UtcNow.ToString('o')) }
    catch { $watch.Stop(); Write-Host ("CASE FAIL: {0} elapsed={1:N2}s ended={2} -- {3}" -f $Name,$watch.Elapsed.TotalSeconds,[DateTime]::UtcNow.ToString('o'),$_.Exception.Message); throw }
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
    Failure-Case 'merge in progress' { param($f) Set-Content (Join-Path $f.Local .git/MERGE_HEAD) ('0' * 40) }
    Failure-Case 'cherry-pick in progress' { param($f) Set-Content (Join-Path $f.Local .git/CHERRY_PICK_HEAD) ('0' * 40) }
    Failure-Case 'rebase in progress' { param($f) New-Item -ItemType Directory (Join-Path $f.Local .git/rebase-merge) | Out-Null }
    Failure-Case 'origin mismatch' { param($f) G $f.Local remote set-url origin (Join-Path $f.Folder wrong.git) }
    Failure-Case 'main absent' { param($f) G $f.Local switch -c temporary; G $f.Local branch -D main }
    Failure-Case 'diverged local main' { param($f) Set-Content (Join-Path $f.Local local.txt) x; G $f.Local add local.txt; G $f.Local -c user.email=x@y -c user.name=x commit -m local-ahead }
    Failure-Case 'main used by another worktree' { param($f) G $f.Local fetch origin issue-66:issue-66; G $f.Local switch issue-66; G $f.Local worktree add (Join-Path $f.Folder main-worktree) main }
    Failure-Case 'remote retrieval failure' { param($f) Remove-Item -LiteralPath $f.Bare -Recurse -Force }
    Run-Case 'origin main advances after target validation race' {
        $f=New-Fixture; $phase=Join-Path $f.Folder phase; $stdout=Join-Path $f.Folder stdout; $stderr=Join-Path $f.Folder stderr
        Set-Content (Join-Path $f.Local protected.txt) keep
        $oldPhase=$env:LANGBENCH_SYNC_TEST_PHASE_DIRECTORY; $env:LANGBENCH_SYNC_TEST_PHASE_DIRECTORY=$phase
        try {
            $arguments=@('-NoProfile','-File',$script,'-RepositoryPath',$f.Local,'-TargetSha',$f.Target,'-MergeSha',$f.Target,'-PullRequestHeadSha',$f.PrHead,'-PullRequestNumber','67','-AllowedRemote',$f.Bare)
            $process=Start-Process pwsh -ArgumentList $arguments -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        } finally { $env:LANGBENCH_SYNC_TEST_PHASE_DIRECTORY=$oldPhase }
        $deadline=[DateTime]::UtcNow.AddSeconds(20)
        while (-not (Test-Path (Join-Path $phase target-validated))) {
            if ([DateTime]::UtcNow -ge $deadline) { $process.Kill(); throw 'race phase was not reached' }
            Start-Sleep -Milliseconds 50
        }
        Set-Content (Join-Path $f.Seed advanced.txt) x; G $f.Seed add advanced.txt; G $f.Seed commit -m advanced; G $f.Seed push origin main
        $newRemote=(& git -C $f.Seed rev-parse HEAD).Trim(); Set-Content (Join-Path $phase continue) continue
        if (-not $process.WaitForExit(30000)) { $process.Kill(); throw 'race child process timed out' }
        $output=Get-Content $stdout -Raw -ErrorAction SilentlyContinue
        if ($process.ExitCode -eq 0 -or $output -match 'status=success') { throw 'race was incorrectly reported as success' }
        if ((& git --git-dir=$($f.Bare) rev-parse refs/heads/main).Trim() -ne $newRemote) { throw 'remote did not advance' }
        if ((& git -C $f.Local rev-parse HEAD).Trim() -ne $f.Target) { throw 'local did not remain at validated target' }
        if ((Get-Content (Join-Path $f.Local protected.txt)) -ne 'keep') { throw 'protected data changed in race' }
    }
    Run-Case 'hooks and fsmonitor suppressed' {
        $f=New-Fixture; $sentinel=Join-Path $f.Folder sentinel; $hook=Join-Path $f.Local .git/hooks/post-merge
        Set-Content $hook "#!/bin/sh`necho hook > '$($sentinel.Replace('\','/'))'"; G $f.Local config core.fsmonitor "echo fsmonitor > '$($sentinel.Replace('\','/'))'"
        Invoke-Sync $f; if (Test-Path $sentinel) { throw 'hook or fsmonitor unexpectedly executed' }
    }
    Failure-Case 'repository-local filter refused' { param($f) G $f.Local config filter.unsafe.smudge 'unsafe-command' }
    Run-Case 'global filter refused' {
        $f=New-Fixture; $config=Join-Path $f.Folder global.gitconfig
        Set-Content $config @('[filter "unsafe"]',' smudge = unsafe-command')
        $old=$env:GIT_CONFIG_GLOBAL; $env:GIT_CONFIG_GLOBAL=$config
        try { Invoke-Sync $f -Fail } finally { $env:GIT_CONFIG_GLOBAL=$old }
    }
    Failure-Case 'worktree filter refused' { param($f) G $f.Local config extensions.worktreeConfig true; G $f.Local config --worktree filter.unsafe.process unsafe-command }
    Failure-Case 'unsafe target gitattributes refused' { param($f) Set-Content (Join-Path $f.Seed .gitattributes) '*.txt filter=unsafe'; G $f.Seed add .gitattributes; G $f.Seed commit -m attributes; G $f.Seed push origin main; $f.Target=(& git -C $f.Seed rev-parse HEAD).Trim() }
    Failure-Case 'target gitlink refused' { param($f) G $f.Seed update-index --add --cacheinfo "160000,$($f.PrHead),nested"; G $f.Seed commit -m gitlink; G $f.Seed push origin main; $f.Target=(& git -C $f.Seed rev-parse HEAD).Trim() }
    Run-Case 'lock conflict' { $f=New-Fixture; $lock=[IO.File]::Open((Join-Path $f.Local '.git/langbench-operation.lock'),'OpenOrCreate','ReadWrite','None'); try { Invoke-Sync $f -Fail } finally { $lock.Dispose() } }
    $suiteWatch.Stop(); $slowest=$caseTimes.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 1
    Write-Host ("sync_local_main tests passed: {0} total={1:N2}s slowest={2} elapsed={3:N2}s" -f $passed,$suiteWatch.Elapsed.TotalSeconds,$slowest.Key,$slowest.Value)
} finally {
    Set-Location -LiteralPath $originalLocation
    Remove-Item -LiteralPath $sandbox -Recurse -Force -ErrorAction SilentlyContinue
}
