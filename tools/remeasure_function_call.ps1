param(
    [ValidateRange(1, 100)][int]$Count = 10,
    [string]$OutputDirectory = "results/diagnostics/function-call-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot
try {
    $output = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
    [System.IO.Directory]::CreateDirectory($output) | Out-Null
    $tracked = @(& git ls-files -- 'benchmarks/function_call_numeric_sum/**' 'experiments/function_call_numeric_sum.json' 'artifacts/function-call-analysis/**' 'tools/*.py')
    if ($LASTEXITCODE -ne 0 -or $tracked.Count -eq 0) { throw 'Cannot identify tracked benchmark inputs.' }
    $inputs = @($tracked | ForEach-Object { Join-Path $projectRoot $_ }) + @($PSCommandPath)
    function Get-InputHashes {
        @($inputs | ForEach-Object { "$_=$((Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash)" })
    }
    $baseline = (Get-InputHashes) -join "`n"
    $head = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot identify Git HEAD.' }

    function Get-TerminalState {
        $state = [ordered]@{ captured_at = (Get-Date).ToString('o');
            active_power_scheme = '未取得'; free_physical_memory_mb = '未取得';
            process_count = '未取得'; cpu_load_percent = '未取得'; ac_power = '未取得' }
        try { $state.active_power_scheme = ((& powercfg /getactivescheme 2>$null) -join ' ').Trim() } catch { }
        if (-not $state.active_power_scheme) { $state.active_power_scheme = '未取得' }
        try {
            $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
            $state.free_physical_memory_mb = [math]::Round($os.FreePhysicalMemory / 1024, 1)
        } catch { }
        try { $state.process_count = @(Get-Process -ErrorAction Stop).Count } catch { }
        return $state
    }

    $record = [ordered]@{ schema_version = '1.0'; benchmark = 'function_call_numeric_sum';
        git_head = $head; execution_order = @('python', 'javascript', 'c/direct', 'c/function_call');
        requested_runs = $Count; successful_runs = 0; runs = @() }
    $recordPath = Join-Path $output 'runs.json'
    for ($number = 1; $number -le $Count; $number++) {
        if (((Get-InputHashes) -join "`n") -cne $baseline) { throw "Benchmark inputs changed before run $number." }
        $experimentId = "$(Get-Date -Format 'yyyyMMdd_HHmmss')_function_call_numeric_sum"
        $logPath = Join-Path $output ('run-{0:D2}.log' -f $number)
        $run = [ordered]@{ order = $number; started_at = (Get-Date).ToString('o'); ended_at = $null;
            status = 'failed'; exit_code = $null; reason = $null; experiment_id = $experimentId;
            archive_id = $null; archive_path = $null; log_path = $logPath;
            terminal_before = (Get-TerminalState); terminal_after = $null }
        try {
            & pwsh -NoProfile -File benchmarks/function_call_numeric_sum/run_all.ps1 -ExperimentId $experimentId *> $logPath
            $run.exit_code = $LASTEXITCODE
            if ($run.exit_code -ne 0) { throw "run_all.ps1 exited $($run.exit_code)" }
            $content = Get-Content -LiteralPath $logPath
            $archiveLines = @($content | Where-Object { $_ -match '^archive_path=' })
            if ($archiveLines.Count -ne 1 -or $content -notcontains 'status=success') {
                throw 'Expected one archive_path and status=success in run output.'
            }
            $archivePath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot ($archiveLines[0] -replace '^archive_path=', '')))
            $diagnosticPath = Join-Path $output ('run-{0:D2}-samples.json' -f $number)
            & python -B tools/show_archive_samples.py --json --all-languages $archivePath > $diagnosticPath
            if ($LASTEXITCODE -ne 0) { throw 'Saved archive failed SHA-256, Validator, or definition validation.' }
            $diagnostic = Get-Content -LiteralPath $diagnosticPath -Raw | ConvertFrom-Json
            if ($diagnostic.runs.Count -ne 1 -or $diagnostic.runs[0].experiment_id -ne $experimentId) {
                throw 'Saved archive identity does not match this run.'
            }
            if (@($record.runs | Where-Object { $_.archive_id -eq $diagnostic.runs[0].archive_id }).Count -ne 0) {
                throw 'Saved archive_id duplicates an earlier run.'
            }
            $run.archive_id = $diagnostic.runs[0].archive_id
            $run.archive_path = $archivePath
            $run.status = 'success'
            $record.successful_runs++
        } catch {
            $run.reason = $_.Exception.Message
        } finally {
            $run.ended_at = (Get-Date).ToString('o')
            $run.terminal_after = Get-TerminalState
            $record.runs += $run
            $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $recordPath -Encoding utf8
            Write-Host "run=$number status=$($run.status) experiment_id=$experimentId archive_id=$($run.archive_id)"
        }
        if (((Get-InputHashes) -join "`n") -cne $baseline) { throw "Benchmark inputs changed after run $number." }
    }
    Write-Host "record_path=$recordPath"
    Write-Host "successful_runs=$($record.successful_runs)/$Count"
    if ($record.successful_runs -ne $Count) { exit 1 }
} finally {
    Pop-Location
}
