$ErrorActionPreference = "Stop"

function Format-CommandPart {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value -match '[\s"]') {
        return '"' + $Value.Replace('"', '""') + '"'
    }
    return $Value
}

$scriptDir = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$sourcePath = (Resolve-Path (Join-Path $scriptDir "main.c")).Path
$exePath = Join-Path $scriptDir "main.exe"
$resultsDir = Join-Path $projectRoot "results"
$resultPath = Join-Path $resultsDir "jit_object_numeric_sum_c_result.json"
[System.IO.Directory]::CreateDirectory($resultsDir) | Out-Null

$gccCommand = Get-Command gcc -ErrorAction SilentlyContinue
if ($null -eq $gccCommand) {
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=gcc was not found in PATH")
    exit 1
}

$compilerVersion = (& gcc --version | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($compilerVersion)) {
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=failed to obtain GCC version")
    exit 1
}

$gccArgs = @($sourcePath, "-O2", "-std=c11", "-Wall", "-Wextra", "-o", $exePath)
$compileCommand = "gcc " + (($gccArgs | ForEach-Object { Format-CommandPart $_ }) -join " ")
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
& gcc @gccArgs
$compileExitCode = $LASTEXITCODE
$stopwatch.Stop()
$compileMs = [Math]::Round($stopwatch.Elapsed.TotalMilliseconds, 3)

if ($compileExitCode -ne 0) {
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=gcc failed with exit code $compileExitCode")
    exit $compileExitCode
}

Push-Location $projectRoot
try {
    $firstProcessStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $firstOutput = & $exePath $compileMs $compilerVersion $compileCommand $sourcePath
    $firstExitCode = $LASTEXITCODE
    $firstProcessStopwatch.Stop()

    if ($firstExitCode -ne 0) {
        $firstOutput | ForEach-Object { Write-Host $_ }
        [Console]::Error.WriteLine("status=error")
        [Console]::Error.WriteLine("message=first benchmark process failed with exit code $firstExitCode")
        exit $firstExitCode
    }

    $repeatProcessStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $repeatOutput = & $exePath $compileMs $compilerVersion $compileCommand $sourcePath
    $repeatExitCode = $LASTEXITCODE
    $repeatProcessStopwatch.Stop()
} finally {
    Pop-Location
}

if ($repeatExitCode -ne 0) {
    $repeatOutput | ForEach-Object { Write-Host $_ }
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=repeat benchmark process failed with exit code $repeatExitCode")
    exit $repeatExitCode
}

$firstProcessTotalMs = [Math]::Round($firstProcessStopwatch.Elapsed.TotalMilliseconds, 3)
$repeatProcessTotalMs = [Math]::Round($repeatProcessStopwatch.Elapsed.TotalMilliseconds, 3)
$buildAndFirstProcessTotalMs = [Math]::Round($compileMs + $firstProcessTotalMs, 3)
$result = Get-Content -Raw -Encoding UTF8 -LiteralPath $resultPath | ConvertFrom-Json
$benchmarkTotalMs = [Math]::Round([double](($result.results | Measure-Object -Property elapsed_ms -Sum).Sum), 3)
$timing = [ordered]@{
    compile_ms = $compileMs
    first_process_total_ms = $firstProcessTotalMs
    repeat_process_total_ms = $repeatProcessTotalMs
    build_and_first_process_total_ms = $buildAndFirstProcessTotalMs
    setup_ms = $result.setup_ms
    warmup_ms = $result.warmup_ms
    benchmark_total_ms = $benchmarkTotalMs
}

if ($result.PSObject.Properties.Name -contains "timing") {
    $result.timing = $timing
} else {
    $result | Add-Member -MemberType NoteProperty -Name timing -Value $timing
}

$json = $result | ConvertTo-Json -Depth 32
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($resultPath, $json + [Environment]::NewLine, $utf8NoBom)

Write-Host "status=success"
Write-Host "compile_ms=$compileMs"
Write-Host "first_process_total_ms=$firstProcessTotalMs"
Write-Host "repeat_process_total_ms=$repeatProcessTotalMs"
Write-Host "build_and_first_process_total_ms=$buildAndFirstProcessTotalMs"
exit 0
