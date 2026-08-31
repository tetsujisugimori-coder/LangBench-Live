param(
    [string]$ExperimentId,
    [string]$RunId
)

$ErrorActionPreference = "Stop"

function Format-CommandPart {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value -match '[\s"]') {
        return '"' + $Value.Replace('"', '""') + '"'
    }
    return $Value
}

function Compare-AnalysisCondition {
    param($Analysis, $Current)
    $mismatches = [System.Collections.Generic.List[string]]::new()
    if ($Analysis.source_sha256 -ne $Current.source_sha256) { $mismatches.Add("source_sha256") }
    if ($Analysis.implementation.name -ne $Current.implementation.name) { $mismatches.Add("implementation.name") }
    if ($Analysis.implementation.version -ne $Current.implementation.version) { $mismatches.Add("implementation.version") }
    if ($Analysis.architecture -ne $Current.architecture) { $mismatches.Add("architecture") }
    if (($Analysis.options | ConvertTo-Json -Compress) -ne ($Current.options | ConvertTo-Json -Compress)) { $mismatches.Add("options") }
    return @($mismatches)
}

$scriptDir = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$sourcePath = (Resolve-Path (Join-Path $scriptDir "main.c")).Path
$manifestPath = Join-Path $projectRoot "artifacts\function-call-analysis\manifest.json"
$exePath = Join-Path ([System.IO.Path]::GetTempPath()) ("langbench-function-call-{0}.exe" -f [guid]::NewGuid().ToString("N"))
$resultsDir = Join-Path $projectRoot "results"
$resultPath = Join-Path $resultsDir "function_call_numeric_sum_c_result.json"
[System.IO.Directory]::CreateDirectory($resultsDir) | Out-Null

$gccCommand = Get-Command gcc -ErrorAction SilentlyContinue
if ($null -eq $gccCommand) {
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=gcc was not found in PATH")
    exit 1
}

$compilerVersionOutput = @(& gcc --version)
$compilerVersionExitCode = $LASTEXITCODE
$compilerVersion = $compilerVersionOutput[0]
if ($compilerVersionExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($compilerVersion)) {
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=failed to obtain GCC version")
    exit 1
}
$compilerVersion = $compilerVersion -replace '^gcc\.exe ', 'gcc '

$optimizationArgs = @("-O2", "-std=c11", "-Wall", "-Wextra")
$gccArgs = @($sourcePath) + $optimizationArgs + @("-o", $exePath)
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

$currentCondition = [ordered]@{
    source_sha256 = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    implementation = [ordered]@{ name = "GCC"; version = $compilerVersion }
    architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
    options = $optimizationArgs
}
try {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $entry = $manifest.languages.c
    $mismatches = @(Compare-AnalysisCondition $entry.condition $currentCondition)
    $matched = $mismatches.Count -eq 0
    $provenance = [ordered]@{
        status = if ($matched) { "matched" } else { "mismatched" }
        artifact_id = $entry.artifact_id
        analyzed_at = $entry.analyzed_at
        applies_to = @($entry.applies_to)
        analysis = $entry.condition
        current = $currentCondition
        matched = $matched
        mismatches = $mismatches
    }
} catch {
    $provenance = [ordered]@{
        status = "unavailable"
        artifact_id = $null
        analyzed_at = $null
        applies_to = @("inlining", "vectorization", "simd")
        analysis = $null
        current = $currentCondition
        matched = $false
        mismatches = @("manifest_unavailable")
    }
}
$provenanceJson = $provenance | ConvertTo-Json -Depth 8 -Compress

Push-Location $projectRoot
try {
    $benchmarkArgs = @($compileMs, $compilerVersion, $compileCommand, $sourcePath, $provenanceJson, $provenance.status)
    if (-not [string]::IsNullOrWhiteSpace($ExperimentId)) {
        $benchmarkArgs += "--experiment-id=$ExperimentId"
    }
    if (-not [string]::IsNullOrWhiteSpace($RunId)) {
        $benchmarkArgs += "--run-id=$RunId"
    }
    $benchmarkOutput = & $exePath @benchmarkArgs
    $benchmarkExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($benchmarkExitCode -ne 0) {
    $benchmarkOutput | ForEach-Object { Write-Host $_ }
    Remove-Item -LiteralPath $exePath -Force -ErrorAction SilentlyContinue
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=benchmark process failed with exit code $benchmarkExitCode")
    exit $benchmarkExitCode
}

if (-not (Test-Path -LiteralPath $resultPath)) {
    Remove-Item -LiteralPath $exePath -Force -ErrorAction SilentlyContinue
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=result JSON was not created")
    exit 1
}

$benchmarkOutput | ForEach-Object { Write-Host $_ }
Write-Host "compile_ms=$compileMs"
Remove-Item -LiteralPath $exePath -Force -ErrorAction SilentlyContinue
exit 0
