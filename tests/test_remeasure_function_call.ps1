$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$fixture = Join-Path $env:RUNNER_TEMP "remeasure-function-call-$([guid]::NewGuid().ToString('N'))"
$repo = Join-Path $fixture 'repo'
$baselineSha = '7cc2c489425358a3694e7e802a8b1356b77ad3fd'

function Git([string[]]$Arguments) {
    $result = & git.exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git failed: $($Arguments -join ' ')" }
    return $result
}

function Invoke-Remeasure(
    [string]$Name,
    [int]$Count,
    [string]$Order = 'direct_first',
    [switch]$BalancedOrder,
    [int]$FailAt = 0,
    [string]$Script = (Join-Path $repo 'tools/remeasure_function_call.ps1')
) {
    $output = "results/fixture/$Name"
    $seriesId = "fixture-$Name"
    $recordOutput = if ($BalancedOrder) {
        "results/diagnostics/balanced-order/$seriesId"
    } else { $output }
    $trace = Join-Path $fixture "$Name-trace.jsonl"
    $env:LANGBENCH_FIXTURE_TRACE = $trace
    $env:LANGBENCH_FIXTURE_FAIL_AT = if ($FailAt) { [string]$FailAt } else { $null }
    $arguments = @('-NoProfile', '-File', $Script, '-Count', $Count, '-MeasurementOrder', $Order,
        '-OutputDirectory', $output)
    if ($BalancedOrder) { $arguments += @('-BalancedOrder', '-SeriesId', $seriesId) }
    $processLog = Join-Path $fixture "$Name.log"
    Push-Location $repo
    try {
        # remeasure's .NET lock path is relative to the child process working
        # directory, so launch it from the same project root used in production.
        & pwsh @arguments *> $processLog
        $exitCode = $LASTEXITCODE
    } finally { Pop-Location }
    $recordPath = Join-Path $repo "$recordOutput/runs.json"
    $record = if (Test-Path -LiteralPath $recordPath) {
        Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    } else { $null }
    $calls = @(if (Test-Path -LiteralPath $trace) {
        @(Get-Content -LiteralPath $trace | ForEach-Object { $_ | ConvertFrom-Json })
    } else { @() })
    return [pscustomobject]@{ ExitCode=$exitCode; Record=$record; Calls=$calls;
        Output=(Join-Path $repo $recordOutput); RecordPath=$recordPath; ProcessLog=$processLog }
}

function Assert-Equal($Actual, $Expected, [string]$Message) {
    if (($Actual | ConvertTo-Json -Compress) -cne ($Expected | ConvertTo-Json -Compress)) {
        throw "$Message`nactual: $($Actual | ConvertTo-Json -Compress)`nexpected: $($Expected | ConvertTo-Json -Compress)"
    }
}

function Assert-PlanAndRuns($Result, [string[]]$Plan, [string]$Message) {
    if ($Result.Record.planned_orders -isnot [System.Array] -or
        $Result.Record.planned_orders.Count -ne $Plan.Count -or
        $Result.Record.runs.Count -ne $Plan.Count -or $Result.Calls.Count -ne $Plan.Count) {
        throw "$Message plan, run record, or child-call count differs from $($Plan.Count)."
    }
    if (-not (Test-Path -LiteralPath $Result.RecordPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $Result.ProcessLog -PathType Leaf)) {
        throw "$Message did not retain its formal record and process log."
    }
    for ($index = 0; $index -lt $Plan.Count; $index++) {
        $run = $Result.Record.runs[$index]
        if ([string]$Result.Record.planned_orders[$index] -cne $Plan[$index] -or
            [string]$Result.Calls[$index].measurement_order -cne $Plan[$index] -or
            [string]$run.requested_order -cne $Plan[$index] -or
            [string]$run.actual_order -cne $Plan[$index] -or $run.status -cne 'success') {
            throw "$Message order/status mismatch at run $($index + 1)."
        }
        if (-not (Test-Path -LiteralPath $run.log_path -PathType Leaf) -or
            -not (Test-Path -LiteralPath $run.archive_path -PathType Container)) {
            throw "$Message did not retain the log or successful archive for run $($index + 1)."
        }
    }
}

New-Item -ItemType Directory -Path $fixture | Out-Null
try {
    Git @('clone', '--no-local', $root, $repo) | Out-Null
    Copy-Item -LiteralPath (Join-Path $root 'tools/remeasure_function_call.ps1') `
        -Destination (Join-Path $repo 'tools/remeasure_function_call.ps1') -Force
    $runner = Join-Path $repo 'benchmarks/function_call_numeric_sum/run_all.ps1'
    @'
param(
    [Parameter(Mandatory)][string]$ExperimentId,
    [string]$MeasurementOrder
)
$ErrorActionPreference = 'Stop'
$trace = $env:LANGBENCH_FIXTURE_TRACE
$callNumber = if (Test-Path -LiteralPath $trace) { @(Get-Content -LiteralPath $trace).Count + 1 } else { 1 }
[ordered]@{ experiment_id=$ExperimentId; measurement_order=$MeasurementOrder } |
    ConvertTo-Json -Compress | Add-Content -LiteralPath $trace -Encoding utf8
if ($MeasurementOrder -notin @('direct_first','function_call_first')) { exit 64 }
if ($env:LANGBENCH_FIXTURE_FAIL_AT -and $callNumber -eq [int]$env:LANGBENCH_FIXTURE_FAIL_AT) { exit 23 }
$archiveRelative = "results/fixture-archives/archive-$([guid]::NewGuid().ToString('N'))"
$archive = Join-Path (Get-Location) $archiveRelative
New-Item -ItemType Directory -Path $archive | Out-Null
$cases = if ($MeasurementOrder -eq 'direct_first') { @('direct','function_call') } else { @('function_call','direct') }
[ordered]@{ experiment_id=$ExperimentId; measurement_order=$cases } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $archive 'experiment.json') -Encoding utf8
Write-Output "archive_path=$archiveRelative"
Write-Output 'status=success'
'@ | Set-Content -LiteralPath $runner -Encoding utf8
    @'
import json, pathlib, sys
archive = pathlib.Path(sys.argv[-1])
definition = json.loads((archive / "experiment.json").read_text(encoding="utf-8-sig"))
print(json.dumps({"runs": [{"experiment_id": definition["experiment_id"], "archive_id": archive.name}]}))
'@ | Set-Content -LiteralPath (Join-Path $repo 'tools/show_archive_samples.py') -Encoding utf8
    Git @('-C', $repo, 'add', 'benchmarks/function_call_numeric_sum/run_all.ps1',
        'tools/remeasure_function_call.ps1', 'tools/show_archive_samples.py') | Out-Null
    Git @('-C', $repo, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-m', 'Install remeasure child-process fixture') | Out-Null

    # Run the exact pre-fix orchestrator from the approved main SHA. This distinguishes
    # the historical code reproduction from unavailable runner-internal logs.
    $beforeScript = Join-Path $repo 'tools/remeasure_function_call.before-issue77.ps1'
    Git @('-C', $root, 'show', "${baselineSha}:tools/remeasure_function_call.ps1") |
        Set-Content -LiteralPath $beforeScript -Encoding utf8
    foreach ($order in @('direct_first', 'function_call_first')) {
        $before = Invoke-Remeasure -Name "before-$order" -Count 1 -Order $order -Script $beforeScript
        if ($before.ExitCode -ne 1 -or $before.Record.successful_runs -ne 0) {
            throw "Pre-fix Count=1/$order did not reproduce the orchestrator failure."
        }
        if ($before.Record.planned_orders -isnot [string] -or
            $before.Record.planned_orders.Count -ne 1 -or $before.Record.planned_orders.Length -ne $order.Length -or
            $before.Record.planned_orders -cne $order -or $before.Record.requested_runs -ne 1) {
            throw "Pre-fix Count=1/$order did not retain the expected scalar plan and complete value."
        }
        $expectedFragment = if ($order -eq 'direct_first') { 'd' } else { 'f' }
        Assert-Equal @($before.Calls | ForEach-Object measurement_order) @($expectedFragment) `
            "Pre-fix Count=1/$order did not pass the reproduced one-character argument."
        if (-not (Test-Path -LiteralPath $before.RecordPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $before.ProcessLog -PathType Leaf) -or
            -not (Test-Path -LiteralPath $before.Record.runs[0].log_path -PathType Leaf) -or
            $null -ne $before.Record.runs[0].actual_order -or $before.Record.runs[0].archive_path) {
            throw "Pre-fix Count=1/$order did not retain its failure evidence cleanly."
        }
    }

    foreach ($order in @('direct_first', 'function_call_first')) {
        $one = Invoke-Remeasure -Name "one-$order" -Count 1 -Order $order
        if ($one.ExitCode -ne 0 -or $one.Record.successful_runs -ne 1) { throw "Count=1/$order failed." }
        Assert-PlanAndRuns $one ([string[]]@($order)) "Count=1/$order"
        $json = Get-Content -LiteralPath (Join-Path $one.Output 'runs.json') -Raw
        if ($json -notmatch '"planned_orders"\s*:\s*\[') { throw "Count=1/$order planned_orders is not JSON array syntax." }
    }

    $multiplePlan = @('function_call_first','function_call_first','function_call_first')
    $multiple = Invoke-Remeasure -Name 'multiple' -Count 3 -Order 'function_call_first'
    if ($multiple.ExitCode -ne 0 -or $multiple.Record.successful_runs -ne 3) { throw 'Multiple-count run failed.' }
    Assert-PlanAndRuns $multiple ([string[]]$multiplePlan) 'Multiple-count'

    $balancedPlan = @('direct_first','function_call_first','function_call_first','direct_first') * 3
    $balanced = Invoke-Remeasure -Name 'balanced' -Count 2 -BalancedOrder
    if ($balanced.ExitCode -ne 0 -or $balanced.Record.requested_runs -ne 12 -or $balanced.Record.successful_runs -ne 12) {
        throw 'Balanced run did not retain its fixed twelve-run contract.'
    }
    Assert-PlanAndRuns $balanced ([string[]]$balancedPlan) 'Balanced D,F,F,D x3'

    $failed = Invoke-Remeasure -Name 'failure' -Count 3 -Order 'direct_first' -FailAt 2
    if ($failed.ExitCode -ne 1 -or $failed.Record.successful_runs -ne 1 -or $failed.Record.runs.Count -ne 2 -or
        $failed.Record.runs[1].exit_code -ne 23 -or $failed.Record.runs[1].status -cne 'failed' -or
        $null -ne $failed.Record.runs[1].actual_order) {
        throw 'Child-process failure, successful_runs, or final exit code was not propagated.'
    }
    Assert-Equal @($failed.Calls | ForEach-Object measurement_order) @('direct_first','direct_first') 'Failure fixture invoked an unexpected plan.'
    if (-not (Test-Path -LiteralPath $failed.RecordPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $failed.ProcessLog -PathType Leaf) -or
        -not (Test-Path -LiteralPath $failed.Record.runs[0].log_path -PathType Leaf) -or
        -not (Test-Path -LiteralPath $failed.Record.runs[0].archive_path -PathType Container) -or
        -not (Test-Path -LiteralPath $failed.Record.runs[1].log_path -PathType Leaf)) {
        throw 'Failure fixture did not retain its process log, record, run logs, or successful archive.'
    }

    $collision = Join-Path $repo 'results/fixture/collision'
    New-Item -ItemType Directory -Path $collision | Out-Null
    $sentinel = Join-Path $collision 'preserve.txt'
    Set-Content -LiteralPath $sentinel -Value 'preserve-existing-output' -Encoding utf8
    $collisionResult = Invoke-Remeasure -Name 'collision' -Count 1
    if ($collisionResult.ExitCode -eq 0 -or (Get-Content -LiteralPath $sentinel -Raw).Trim() -cne 'preserve-existing-output') {
        throw 'Output collision was not rejected without modifying existing data.'
    }

    $common = [IO.Path]::GetFullPath((Git @('-C', $repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')).Trim())
    Push-Location $repo
    try {
        # Resolve the path exactly as the formal orchestrator does. PowerShell's
        # location and a child process working directory are distinct boundaries.
        $orchestratorLockPath = (& pwsh -NoProfile -Command @'
$gitDirectory = (& git rev-parse --git-common-dir).Trim()
if ($LASTEXITCODE -ne 0) { exit 91 }
[IO.Path]::GetFullPath((Join-Path $gitDirectory 'langbench-operation.lock'))
'@).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the orchestrator Git common directory.' }
    } finally { Pop-Location }
    $lockPath = [IO.Path]::GetFullPath((Join-Path $common 'langbench-operation.lock'))
    if ($lockPath -ine $orchestratorLockPath) {
        throw "Fixture/orchestrator lock paths differ: fixture=$lockPath orchestrator=$orchestratorLockPath"
    }
    $lock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $locked = Invoke-Remeasure -Name 'locked' -Count 1
        $lockedOutputExists = Test-Path -LiteralPath $locked.Output
        if ($locked.ExitCode -eq 0) {
            throw "Operation-lock child exit code was zero: exit_code=$($locked.ExitCode) output_exists=$lockedOutputExists lock=$lockPath"
        }
        if ($lockedOutputExists) {
            throw "Operation-lock output was created: exit_code=$($locked.ExitCode) output_exists=$lockedOutputExists output=$($locked.Output) lock=$lockPath"
        }
    } finally { $lock.Dispose() }
} finally {
    $env:LANGBENCH_FIXTURE_TRACE = $null
    $env:LANGBENCH_FIXTURE_FAIL_AT = $null
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
Write-Host 'remeasure function-call orchestration regression: valid'
