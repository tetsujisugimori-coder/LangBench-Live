param(
    [string]$OutputDirectory = "results/diagnostics/c-order-followup-$(Get-Date -Format 'yyyyMMdd_HHmmss')",
    [switch]$PlanOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $projectRoot 'tools/source_hash.ps1')
$planText = (& python -B (Join-Path $projectRoot 'tools/c_order_followup.py') --print-plan) -join "`n"
if ($LASTEXITCODE -ne 0) { throw 'Cannot create the fixed 40-run plan.' }
if ($PlanOnly) { Write-Output $planText; exit 0 }
$plan = @($planText | ConvertFrom-Json)

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
    $lock = [System.IO.File]::Open((Join-Path $projectRoot 'results/function_call_numeric_sum.lock'),
        [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $sourcePath = Join-Path $projectRoot 'benchmarks/function_call_numeric_sum/c/main.c'
    $head = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot identify Git HEAD.' }
    $sourceHash = Get-CanonicalSourceHash -Path $sourcePath
    $tracked = @(& git ls-files -- 'benchmarks/function_call_numeric_sum/c/**' 'tools/source_hash.ps1' 'tools/validate_result_json.py' 'artifacts/function-call-analysis/**')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot identify benchmark inputs.' }
    $tracked += @('tools/diagnose_c_measurement_order_followup.ps1', 'tools/c_order_followup.py',
        'tools/summarize_c_order_diagnostic.py', 'tools/sample_windows_cpu.py')
    function Get-InputHashes {
        return (@($tracked | ForEach-Object { "$_=$((Get-FileHash -LiteralPath (Join-Path $projectRoot $_) -Algorithm SHA256).Hash)" }) -join "`n")
    }
    $baseline = Get-InputHashes
    $record = [ordered]@{ schema_version = '3.0'; benchmark = 'function_call_numeric_sum';
        git_head = $head; c_source_sha256 = $sourceHash; compiler = 'gcc';
        compiler_options = @('-O2', '-std=c11', '-Wall', '-Wextra'); plan = $plan; runs = @() }
    for ($index = 0; $index -lt $plan.Count; $index++) {
        $item = $plan[$index]
        $record.runs += [ordered]@{ number = $index + 1; pair = $item.pair; position = $item.position;
            order = $item.order; monitored = $item.monitored;
            measurement_order = if ($item.order -eq 'A') { @('direct', 'function_call') } else { @('function_call', 'direct') };
            started_at = $null; ended_at = $null; status = 'pending';
            c_measurement_status = 'pending'; trace_status = 'pending';
            monitor_status = if ($item.monitored) { 'pending' } else { 'not_planned' };
            monitor_launch_status = if ($item.monitored) { 'pending' } else { 'not_planned' };
            monitor_exit_status = if ($item.monitored) { 'pending' } else { 'not_planned' };
            monitor_file_status = if ($item.monitored) { 'pending' } else { 'not_planned' };
            monitor_validation_status = if ($item.monitored) { 'pending' } else { 'not_planned' };
            reason_code = $null; failure_reason = $null; monitor_reason_code = $null;
            monitor_failure_reason = $null; exit_code = $null; monitor_exit_code = $null;
            git_head = $head; c_source_sha256 = $sourceHash;
            compiler = 'gcc'; compiler_options = @('-O2', '-std=c11', '-Wall', '-Wextra');
            terminal_before = $null; terminal_after = $null }
    }
    $recordPath = Join-Path $output 'runs.json'
    $planText | Set-Content -LiteralPath (Join-Path $output 'plan.json') -Encoding utf8
    function Save-Record { $record | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $recordPath -Encoding utf8 }
    Save-Record
    Write-Host "plan_path=$(Join-Path $output 'plan.json') planned_runs=40"
    for ($index = 0; $index -lt 40; $index++) {
        $number = $index + 1
        $run = $record.runs[$index]
        $run.started_at = (Get-Date).ToString('o')
        $run.terminal_before = Get-TerminalState
        $resultPath = Join-Path $output ('run-{0:D2}.json' -f $number)
        $tracePath = Join-Path $output ('run-{0:D2}-trace.json' -f $number)
        $monitorPath = Join-Path $output ('run-{0:D2}-monitor.json' -f $number)
        $monitorReady = Join-Path $output ('run-{0:D2}-monitor.ready' -f $number)
        $monitorStop = Join-Path $output ('run-{0:D2}-monitor.stop' -f $number)
        $logPath = Join-Path $output ('run-{0:D2}.log' -f $number)
        $monitorProcess = $null
        try {
            if ((Get-InputHashes) -cne $baseline -or (Get-CanonicalSourceHash -Path $sourcePath) -ne $sourceHash) {
                throw 'Benchmark inputs changed before this run.'
            }
            if ($run.monitored) {
                try {
                    $python = (Get-Command python -ErrorAction Stop).Source
                    $monitorArgs = @('-B', (Join-Path $projectRoot 'tools/sample_windows_cpu.py'),
                        '--output', $monitorPath, '--ready', $monitorReady, '--stop', $monitorStop, '--interval-ms', '20')
                    $monitorProcess = Start-Process -FilePath $python -ArgumentList $monitorArgs -PassThru -WindowStyle Hidden
                    $deadline = [datetime]::UtcNow.AddSeconds(10)
                    while (-not (Test-Path -LiteralPath $monitorReady) -and -not $monitorProcess.HasExited -and [datetime]::UtcNow -lt $deadline) {
                        Start-Sleep -Milliseconds 10
                    }
                    if (Test-Path -LiteralPath $monitorReady) {
                        $run.monitor_launch_status = 'success'
                    } else {
                        $run.monitor_launch_status = 'failed'
                        $run.monitor_reason_code = 'MONITOR_NOT_READY'
                        $run.monitor_failure_reason = 'CPU monitor did not become ready.'
                    }
                } catch {
                    $run.monitor_launch_status = 'failed'
                    $run.monitor_reason_code = 'MONITOR_LAUNCH_FAILED'
                    $run.monitor_failure_reason = $_.Exception.Message
                }
            }
            $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
            $measurementOrder = if ($run.order -eq 'A') { 'direct_first' } else { 'function_call_first' }
            & pwsh -NoProfile -File benchmarks/function_call_numeric_sum/c/run_c.ps1 `
                -ExperimentId "${timestamp}_function_call_numeric_sum" `
                -RunId "${timestamp}_c_function_call_numeric_sum" -MeasurementOrder $measurementOrder `
                -DiagnosticResultPath $resultPath -DiagnosticTracePath $tracePath *> $logPath
            $run.exit_code = $LASTEXITCODE
            if ($run.exit_code -ne 0) { throw "C runner exited $($run.exit_code)" }
            if (-not (Test-Path -LiteralPath $resultPath)) { throw 'Result JSON was not created.' }
            & python -B tools/summarize_c_order_diagnostic.py --validate-result $resultPath *> (Join-Path $output ('run-{0:D2}-result-validation.log' -f $number))
            if ($LASTEXITCODE -ne 0) { throw 'C result validation failed.' }
            $document = Get-Content -LiteralPath $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ((@($document.execution.measurement_order) -join ',') -ne (@($run.measurement_order) -join ',') -or
                $document.optimization_analysis.provenance.current.source_sha256 -ne $sourceHash -or
                (@($document.optimization_analysis.provenance.current.options) -join ',') -ne ($run.compiler_options -join ',') -or
                $document.config.item_count -ne 1000000 -or $document.config.warmup_iterations -ne 5 -or
                $document.config.measurement_iterations -ne 50) {
                throw 'C result differs from fixed conditions.'
            }
            foreach ($case in @('direct', 'function_call')) {
                if (@($document.results.$case.samples_ms).Count -ne 50 -or $document.validation."${case}_checksum" -ne 500000500000) {
                    throw "$case sample count or checksum differs."
                }
            }
            $run.c_measurement_status = 'success'
            if (-not (Test-Path -LiteralPath $tracePath)) { throw 'C trace was not created.' }
            & python -B tools/summarize_c_order_diagnostic.py --validate-result $resultPath --validate-trace $tracePath *> (Join-Path $output ('run-{0:D2}-trace-validation.log' -f $number))
            if ($LASTEXITCODE -ne 0) { throw 'C trace validation failed.' }
            $run.trace_status = 'success'
        } catch {
            $run.reason_code = if ($run.c_measurement_status -eq 'success') { 'TRACE_FAILED' } else { 'C_MEASUREMENT_FAILED' }
            $run.failure_reason = $_.Exception.Message
            if ($run.trace_status -eq 'pending') { $run.trace_status = 'failed' }
            if ($run.c_measurement_status -eq 'pending') { $run.c_measurement_status = 'failed' }
        } finally {
            if ($run.monitored) {
                if ($null -ne $monitorProcess) {
                    try {
                        [System.IO.File]::WriteAllText($monitorStop, 'stop')
                        if (-not $monitorProcess.WaitForExit(10000)) {
                            $run.monitor_exit_status = 'timeout'
                            $run.monitor_reason_code = 'MONITOR_TIMEOUT'
                            $run.monitor_failure_reason = 'CPU monitor did not exit within 10 seconds.'
                            $monitorProcess.Kill()
                            $monitorProcess.WaitForExit()
                        } else {
                            $run.monitor_exit_code = $monitorProcess.ExitCode
                            $run.monitor_exit_status = if ($monitorProcess.ExitCode -eq 0) { 'success' } else { 'failed' }
                            if ($run.monitor_exit_status -ne 'success') {
                                $run.monitor_reason_code = 'MONITOR_EXIT_FAILED'
                                $run.monitor_failure_reason = "CPU monitor exited $($monitorProcess.ExitCode)."
                            }
                        }
                    } catch {
                        $run.monitor_exit_status = 'failed'
                        $run.monitor_reason_code = 'MONITOR_EXIT_FAILED'
                        $run.monitor_failure_reason = $_.Exception.Message
                    } finally { $monitorProcess.Dispose() }
                } else { $run.monitor_exit_status = 'not_started' }
                $run.monitor_file_status = if (Test-Path -LiteralPath $monitorPath) { 'success' } else { 'missing' }
                if ($run.monitor_file_status -eq 'success') {
                    try {
                        $args = @('-B', 'tools/c_order_followup.py', '--validate-monitor', $monitorPath)
                        if ($run.trace_status -eq 'success') { $args += @('--validate-trace', $tracePath) }
                        & python @args *> (Join-Path $output ('run-{0:D2}-monitor-validation.log' -f $number))
                        if ($LASTEXITCODE -ne 0) { throw 'Monitor content validation failed.' }
                        $run.monitor_validation_status = 'success'
                    } catch {
                        $run.monitor_validation_status = 'failed'
                        $run.monitor_reason_code = 'MONITOR_INVALID'
                        $run.monitor_failure_reason = $_.Exception.Message
                    }
                } else {
                    $run.monitor_validation_status = 'not_available'
                    if ($null -eq $run.monitor_reason_code) {
                        $run.monitor_reason_code = 'MONITOR_FILE_MISSING'
                        $run.monitor_failure_reason = 'Monitor output file is missing.'
                    }
                }
                $run.monitor_status = if ($run.monitor_launch_status -eq 'success' -and
                    $run.monitor_exit_status -eq 'success' -and $run.monitor_file_status -eq 'success' -and
                    $run.monitor_validation_status -eq 'success') { 'recorded' } else { 'failed' }
            }
            $run.status = if ($run.c_measurement_status -eq 'success' -and $run.trace_status -eq 'success') { 'success' } else { 'failed' }
            $run.ended_at = (Get-Date).ToString('o')
            $run.terminal_after = Get-TerminalState
            Save-Record
            Write-Host "run=$number order=$($run.order) monitored=$($run.monitored) c=$($run.c_measurement_status) trace=$($run.trace_status) monitor=$($run.monitor_status)"
        }
    }
    & python -B tools/c_order_followup.py $output --public-output (Join-Path $output 'public-data.json') --table-output (Join-Path $output 'summary.md')
    if ($LASTEXITCODE -ne 0) { throw 'Public data generation failed.' }
    Write-Host "record_path=$recordPath"
    Write-Host "public_data_path=$(Join-Path $output 'public-data.json')"
    $successful = @($record.runs | Where-Object { $_.status -eq 'success' }).Count
    $monitored = @($record.runs | Where-Object { $_.monitor_status -eq 'recorded' }).Count
    Write-Host "c_and_trace_success=$successful/40 monitor_success=$monitored/20"
    if ($successful -ne 40 -or $monitored -ne 20) { exit 1 }
} finally {
    if ($null -ne $lock) { $lock.Dispose() }
    Pop-Location
}
