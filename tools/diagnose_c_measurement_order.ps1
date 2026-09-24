param(
    [string]$OutputDirectory = "results/diagnostics/c-order-$(Get-Date -Format 'yyyyMMdd_HHmmss')",
    [switch]$PlanOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $projectRoot 'tools/source_hash.ps1')
$plan = @()
for ($pair = 1; $pair -le 10; $pair++) {
    $pairOrder = if ($pair % 2 -eq 1) { @('A', 'B') } else { @('B', 'A') }
    foreach ($order in $pairOrder) { $plan += [ordered]@{ pair = $pair; order = $order } }
}
if ($PlanOnly) { $plan | ConvertTo-Json -Depth 3; exit 0 }

function Get-TerminalState {
    $state = [ordered]@{ captured_at = (Get-Date).ToString('o') }
    try {
        $value = ((& powercfg /getactivescheme 2>$null) -join ' ').Trim()
        if ($LASTEXITCODE -eq 0 -and $value) { $state.active_power_scheme = $value }
    } catch { }
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        $state.free_physical_memory_mb = [math]::Round($os.FreePhysicalMemory / 1024, 1)
    } catch { }
    try { $state.process_count = @(Get-Process -ErrorAction Stop).Count } catch { }
    return $state
}

Push-Location $projectRoot
$lock = $null
try {
    $output = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
    if (Test-Path -LiteralPath $output) { throw "Output directory already exists: $output" }
    [System.IO.Directory]::CreateDirectory($output) | Out-Null
    [System.IO.Directory]::CreateDirectory((Join-Path $projectRoot 'results')) | Out-Null
    # The normal runner uses this lock for its fixed result filenames.
    $lock = [System.IO.File]::Open((Join-Path $projectRoot 'results/function_call_numeric_sum.lock'),
        [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $sourcePath = Join-Path $projectRoot 'benchmarks/function_call_numeric_sum/c/main.c'
    $head = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot identify Git HEAD.' }
    $sourceHash = Get-CanonicalSourceHash -Path $sourcePath
    $tracked = @(& git ls-files -- 'benchmarks/function_call_numeric_sum/c/**' 'tools/source_hash.ps1' 'tools/validate_result_json.py' 'artifacts/function-call-analysis/**')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot identify benchmark inputs.' }
    $tracked += @('tools/diagnose_c_measurement_order.ps1', 'tools/summarize_c_order_diagnostic.py')
    function Get-InputHashes {
        return (@($tracked | ForEach-Object { "$_=$((Get-FileHash -LiteralPath (Join-Path $projectRoot $_) -Algorithm SHA256).Hash)" }) -join "`n")
    }
    $baseline = Get-InputHashes
    $record = [ordered]@{ schema_version = '1.0'; benchmark = 'function_call_numeric_sum';
        git_head = $head; c_source_sha256 = $sourceHash;
        compiler = 'gcc'; compiler_options = @('-O2', '-std=c11', '-Wall', '-Wextra');
        plan = $plan; runs = @() }
    $recordPath = Join-Path $output 'runs.json'
    $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $recordPath -Encoding utf8
    for ($index = 0; $index -lt $plan.Count; $index++) {
        $number = $index + 1
        if ((Get-InputHashes) -cne $baseline -or (Get-CanonicalSourceHash -Path $sourcePath) -ne $sourceHash) {
            throw "Benchmark inputs changed before run $number."
        }
        $order = $plan[$index].order
        $measurementOrder = if ($order -eq 'A') { 'direct_first' } else { 'function_call_first' }
        $resultPath = Join-Path $output ('run-{0:D2}.json' -f $number)
        $logPath = Join-Path $output ('run-{0:D2}.log' -f $number)
        $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $run = [ordered]@{ number = $number; pair = $plan[$index].pair; order = $order;
            measurement_order = if ($order -eq 'A') { @('direct', 'function_call') } else { @('function_call', 'direct') };
            started_at = (Get-Date).ToString('o'); ended_at = $null; status = 'failed';
            reason_code = $null; failure_reason = $null; exit_code = $null;
            git_head = $head; c_source_sha256 = $sourceHash;
            compiler = 'gcc'; compiler_options = @('-O2', '-std=c11', '-Wall', '-Wextra');
            terminal_before = (Get-TerminalState); terminal_after = $null }
        try {
            $experimentId = "${timestamp}_function_call_numeric_sum"
            $runId = "${timestamp}_c_function_call_numeric_sum"
            & pwsh -NoProfile -File benchmarks/function_call_numeric_sum/c/run_c.ps1 `
                -ExperimentId $experimentId -RunId $runId -MeasurementOrder $measurementOrder `
                -DiagnosticResultPath $resultPath *> $logPath
            $run.exit_code = $LASTEXITCODE
            if ($run.exit_code -ne 0) { throw "C runner exited $($run.exit_code)" }
            if (-not (Test-Path -LiteralPath $resultPath)) { throw 'Result JSON was not created.' }
            & python -B tools/summarize_c_order_diagnostic.py --validate-result $resultPath *> (Join-Path $output 'validation.log')
            if ($LASTEXITCODE -ne 0) { throw 'Diagnostic validation failed.' }
            $document = Get-Content -LiteralPath $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ((@($document.execution.measurement_order) -join ',') -ne (@($run.measurement_order) -join ',')) {
                throw 'Recorded C execution order differs from the plan.'
            }
            if ($document.optimization_analysis.provenance.current.source_sha256 -ne $sourceHash -or
                (@($document.optimization_analysis.provenance.current.options) -join ',') -ne ($run.compiler_options -join ',')) {
                throw 'C source or compiler options differ from the fixed conditions.'
            }
            foreach ($case in @('direct', 'function_call')) {
                if (@($document.results.$case.samples_ms).Count -ne 50 -or
                    $document.validation."${case}_checksum" -ne 500000500000) {
                    throw "$case sample count or checksum differs."
                }
            }
            $run.status = 'success'
        } catch {
            $run.reason_code = 'RUN_FAILED'
            $run.failure_reason = $_.Exception.Message
        } finally {
            $run.ended_at = (Get-Date).ToString('o')
            $run.terminal_after = Get-TerminalState
            $record.runs += $run
            $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $recordPath -Encoding utf8
            Write-Host "run=$number order=$order status=$($run.status)"
        }
        if ((Get-InputHashes) -cne $baseline) { throw "Benchmark inputs changed after run $number." }
    }
    & python -B tools/summarize_c_order_diagnostic.py $output `
        --public-output (Join-Path $output 'public-data.json') `
        --table-output (Join-Path $output 'summary.md')
    if ($LASTEXITCODE -ne 0) { throw 'Public data generation failed.' }
    Write-Host "record_path=$recordPath"
    Write-Host "public_data_path=$(Join-Path $output 'public-data.json')"
    $successful = @($record.runs | Where-Object { $_.status -eq 'success' }).Count
    Write-Host "successful_runs=$successful/20"
    if ($successful -ne 20) { exit 1 }
} finally {
    if ($null -ne $lock) { $lock.Dispose() }
    Pop-Location
}
