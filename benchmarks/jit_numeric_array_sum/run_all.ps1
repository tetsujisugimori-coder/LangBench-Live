$ErrorActionPreference = "Stop"

function Invoke-MeasuredProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Language,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Write-Host "language=$Language status=started"
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $commandOutput = & $Command @Arguments
    $exitCode = $LASTEXITCODE
    $stopwatch.Stop()
    $processTotalMs = [Math]::Round($stopwatch.Elapsed.TotalMilliseconds, 3)
    $commandOutput | ForEach-Object { Write-Host $_ }

    if ($exitCode -ne 0) {
        [Console]::Error.WriteLine("language=$Language status=error exit_code=$exitCode")
        exit $exitCode
    }

    Write-Host "language=$Language status=success process_total_ms=$processTotalMs"
    return $processTotalMs
}

function Update-ProcessTimingMetadata {
    param(
        [Parameter(Mandatory = $true)][string]$ResultPath,
        [Parameter(Mandatory = $true)][double]$ProcessTotalMs
    )

    if (-not (Test-Path -LiteralPath $ResultPath)) {
        throw "Result JSON was not created: $ResultPath"
    }

    $result = Get-Content -Raw -Encoding UTF8 -LiteralPath $ResultPath | ConvertFrom-Json
    $benchmarkTotalMs = [Math]::Round(
        [double](($result.results | Measure-Object -Property elapsed_ms -Sum).Sum),
        3
    )
    $timing = [ordered]@{
        process_total_ms = $ProcessTotalMs
        build_and_process_total_ms = $null
        setup_ms = $result.setup_ms
        benchmark_total_ms = $benchmarkTotalMs
    }

    if ($result.PSObject.Properties.Name -contains "timing") {
        $result.timing = $timing
    } else {
        $result | Add-Member -MemberType NoteProperty -Name timing -Value $timing
    }

    $json = $result | ConvertTo-Json -Depth 32
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText(
        $ResultPath,
        $json + [Environment]::NewLine,
        $utf8NoBom
    )
}

$scriptDir = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$javascriptPath = (Resolve-Path (Join-Path $scriptDir "javascript\main.js")).Path
$pythonPath = (Resolve-Path (Join-Path $scriptDir "python\main.py")).Path
$cRunnerPath = (Resolve-Path (Join-Path $scriptDir "c\run_c.ps1")).Path
$resultsDir = Join-Path $projectRoot "results"
$resultPaths = @{
    javascript = Join-Path $resultsDir "jit_numeric_array_sum_javascript_result.json"
    python = Join-Path $resultsDir "jit_numeric_array_sum_python_result.json"
}

[System.IO.Directory]::CreateDirectory($resultsDir) | Out-Null

$nodeCommand = (Get-Command node -ErrorAction Stop).Source
$pythonCommand = (Get-Command python -ErrorAction Stop).Source
$powershellCommand = (Get-Command powershell -ErrorAction Stop).Source

# Change this array to adjust the sequential execution order.
$executionOrder = @(
    [pscustomobject]@{
        Language = "javascript"
        Command = $nodeCommand
        Arguments = @($javascriptPath)
        ResultPath = $resultPaths.javascript
        UpdateTiming = $true
    },
    [pscustomobject]@{
        Language = "python"
        Command = $pythonCommand
        Arguments = @($pythonPath)
        ResultPath = $resultPaths.python
        UpdateTiming = $true
    },
    [pscustomobject]@{
        Language = "c"
        Command = $powershellCommand
        Arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $cRunnerPath)
        ResultPath = $null
        UpdateTiming = $false
    }
)

Push-Location $projectRoot
try {
    foreach ($entry in $executionOrder) {
        $processTotalMs = Invoke-MeasuredProcess `
            -Language $entry.Language `
            -Command $entry.Command `
            -Arguments $entry.Arguments

        if ($entry.UpdateTiming) {
            Update-ProcessTimingMetadata `
                -ResultPath $entry.ResultPath `
                -ProcessTotalMs $processTotalMs
        }
    }
} finally {
    Pop-Location
}
