$ErrorActionPreference = 'Stop'
$helper = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'tools/prepare_function_call_fixture_clone.ps1'
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('langbench-analysis-clone-test-' + [guid]::NewGuid().ToString('N'))
function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
try {
    [IO.Directory]::CreateDirectory($tempRoot) | Out-Null
    $mainSource = Join-Path $tempRoot 'source-main'
    & git init -q -b main $mainSource
    if ($LASTEXITCODE -ne 0) { throw 'fixture init failed' }
    & git -C $mainSource config user.email fixture@example.invalid
    & git -C $mainSource config user.name fixture
    [IO.File]::WriteAllText((Join-Path $mainSource 'fixture.txt'), 'fixture')
    & git -C $mainSource add -- fixture.txt
    & git -C $mainSource commit -qm fixture
    if ($LASTEXITCODE -ne 0) { throw 'fixture commit failed' }
    $sha = (& git -C $mainSource rev-parse HEAD).Trim()
    $mainClone = Join-Path $tempRoot 'main-clone'
    & $helper -SourceRepository $mainSource -Destination $mainClone -SourceSha $sha
    Assert-True ($LASTEXITCODE -eq 0 -and (& git -C $mainClone rev-parse HEAD).Trim() -eq $sha) 'main source fixture failed'
    $detachedSource = Join-Path $tempRoot 'source-detached'
    & git clone --quiet --no-local $mainSource $detachedSource
    if ($LASTEXITCODE -ne 0) { throw 'detached source clone failed' }
    & git -C $detachedSource switch --quiet --detach $sha
    & git -C $detachedSource branch -D main | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'detached source branch removal failed' }
    $detachedClone = Join-Path $tempRoot 'detached-clone'
    & $helper -SourceRepository $detachedSource -Destination $detachedClone -SourceSha $sha
    Assert-True ($LASTEXITCODE -eq 0 -and (& git -C $detachedClone rev-parse HEAD).Trim() -eq $sha) 'detached source fixture failed'
    Write-Host 'tests=2 passed=2'
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
