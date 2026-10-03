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
    $trace = Join-Path $fixture "$Name-trace.jsonl"
    $env:LANGBENCH_FIXTURE_TRACE = $trace
    $env:LANGBENCH_FIXTURE_FAIL_AT = if ($FailAt) { [string]$FailAt } else { $null }
    $arguments = @('-NoProfile', '-File', $Script, '-Count', $Count, '-MeasurementOrder', $Order,
        '-OutputDirectory', $output)
    if ($BalancedOrder) { $arguments += '-BalancedOrder' }
    & pwsh @arguments *> (Join-Path $fixture "$Name.log")
    $exitCode = $LASTEXITCODE
    $recordPath = Join-Path $repo "$output/runs.json"
    $record = if (Test-Path -LiteralPath $recordPath) {
        Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    } else { $null }
    $calls = if (Test-Path -LiteralPath $trace) {
        @(Get-Content -LiteralPath $trace | ForEach-Object { $_ | ConvertFrom-Json })
    } else { @() }
    return [pscustomobject]@{ ExitCode=$exitCode; Record=$record; Calls=$calls; Output=(Join-Path $repo $output) }
}

function Assert-Equal($Actual, $Expected, [string]$Message) {
    if (($Actual | ConvertTo-Json -Compress) -cne ($Expected | ConvertTo-Json -Compress)) {
        throw "$Message`nactual: $($Actual | ConvertTo-Json -Compress)`nexpected: $($Expected | ConvertTo-Json -Compress)"
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
$archive = Join-Path (Split-Path -Parent $trace) "archive-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $archive | Out-Null
$cases = if ($MeasurementOrder -eq 'direct_first') { @('direct','function_call') } else { @('function_call','direct') }
[ordered]@{ experiment_id=$ExperimentId; measurement_order=$cases } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $archive 'experiment.json') -Encoding utf8
Write-Output "archive_path=$archive"
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
        $expectedFragment = if ($order -eq 'direct_first') { 'd' } else { 'f' }
        Assert-Equal @($before.Calls | ForEach-Object measurement_order) @($expectedFragment) `
            "Pre-fix Count=1/$order did not pass the reproduced one-character argument."
    }

    foreach ($order in @('direct_first', 'function_call_first')) {
        $one = Invoke-Remeasure -Name "one-$order" -Count 1 -Order $order
        if ($one.ExitCode -ne 0 -or $one.Record.successful_runs -ne 1) { throw "Count=1/$order failed." }
        Assert-Equal @($one.Record.planned_orders) @($order) "Count=1/$order plan is not a one-element array."
        Assert-Equal @($one.Calls | ForEach-Object measurement_order) @($order) "Count=1/$order child argument changed."
        if ($one.Record.runs[0].requested_order -cne $order -or $one.Record.runs[0].actual_order -cne $order) {
            throw "Count=1/$order requested/actual order mismatch."
        }
        $json = Get-Content -LiteralPath (Join-Path $one.Output 'runs.json') -Raw
        if ($json -notmatch '"planned_orders"\s*:\s*\[') { throw "Count=1/$order planned_orders is not JSON array syntax." }
    }

    $multiplePlan = @('function_call_first','function_call_first','function_call_first')
    $multiple = Invoke-Remeasure -Name 'multiple' -Count 3 -Order 'function_call_first'
    if ($multiple.ExitCode -ne 0 -or $multiple.Record.successful_runs -ne 3) { throw 'Multiple-count run failed.' }
    Assert-Equal @($multiple.Record.planned_orders) $multiplePlan 'Multiple-count plan changed.'
    Assert-Equal @($multiple.Calls | ForEach-Object measurement_order) $multiplePlan 'Multiple-count child arguments changed.'

    $balancedPlan = @('direct_first','function_call_first','function_call_first','direct_first') * 3
    $balanced = Invoke-Remeasure -Name 'balanced' -Count 2 -BalancedOrder
    if ($balanced.ExitCode -ne 0 -or $balanced.Record.requested_runs -ne 12 -or $balanced.Record.successful_runs -ne 12) {
        throw 'Balanced run did not retain its fixed twelve-run contract.'
    }
    Assert-Equal @($balanced.Record.planned_orders) $balancedPlan 'Balanced D,F,F,D x3 plan changed.'
    Assert-Equal @($balanced.Calls | ForEach-Object measurement_order) $balancedPlan 'Balanced child arguments changed.'

    $failed = Invoke-Remeasure -Name 'failure' -Count 3 -Order 'direct_first' -FailAt 2
    if ($failed.ExitCode -ne 1 -or $failed.Record.successful_runs -ne 1 -or $failed.Record.runs.Count -ne 2 -or
        $failed.Record.runs[1].exit_code -ne 23 -or $failed.Record.runs[1].status -cne 'failed') {
        throw 'Child-process failure, successful_runs, or final exit code was not propagated.'
    }
    Assert-Equal @($failed.Calls | ForEach-Object measurement_order) @('direct_first','direct_first') 'Failure fixture invoked an unexpected plan.'

    $collision = Join-Path $repo 'results/fixture/collision'
    New-Item -ItemType Directory -Path $collision | Out-Null
    $sentinel = Join-Path $collision 'preserve.txt'
    Set-Content -LiteralPath $sentinel -Value 'preserve-existing-output' -Encoding utf8
    $collisionResult = Invoke-Remeasure -Name 'collision' -Count 1
    if ($collisionResult.ExitCode -eq 0 -or (Get-Content -LiteralPath $sentinel -Raw).Trim() -cne 'preserve-existing-output') {
        throw 'Output collision was not rejected without modifying existing data.'
    }

    $common = (Git @('-C', $repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')).Trim()
    $lock = [IO.File]::Open((Join-Path $common 'langbench-operation.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $locked = Invoke-Remeasure -Name 'locked' -Count 1
        if ($locked.ExitCode -eq 0 -or (Test-Path -LiteralPath $locked.Output)) { throw 'Operation lock did not stop before output creation.' }
    } finally { $lock.Dispose() }
} finally {
    $env:LANGBENCH_FIXTURE_TRACE = $null
    $env:LANGBENCH_FIXTURE_FAIL_AT = $null
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
Write-Host 'remeasure function-call orchestration regression: valid'
