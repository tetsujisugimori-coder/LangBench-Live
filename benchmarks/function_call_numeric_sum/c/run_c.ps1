param(
    [string]$ExperimentId,
    [string]$RunId,
    [string]$AnalysisManifestPath,
    [switch]$ResolveAnalysisOnly
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

function Test-NonEmptyString { param($Value) return $Value -is [string] -and -not [string]::IsNullOrWhiteSpace($Value) }
function Test-JsonObject { param($Value) return $null -ne $Value -and $Value -is [pscustomobject] }
function Test-AnalysisTimestamp {
    param($Value)
    if ($Value -is [datetime]) { return $Value.Kind -ne [System.DateTimeKind]::Unspecified }
    return (Test-NonEmptyString $Value) -and $Value -match '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$'
}
function Test-AnalysisCondition {
    param($Condition)
    if (-not (Test-JsonObject $Condition)) { return $false }
    $names = @($Condition.PSObject.Properties.Name | Sort-Object)
    if (($names -join ",") -ne "architecture,implementation,options,source_sha256") { return $false }
    if (-not (Test-NonEmptyString $Condition.source_sha256) -or $Condition.source_sha256 -notmatch '^[0-9a-f]{64}$') { return $false }
    if (-not (Test-JsonObject $Condition.implementation)) { return $false }
    if ((@($Condition.implementation.PSObject.Properties.Name | Sort-Object) -join ",") -ne "name,version") { return $false }
    if (-not (Test-NonEmptyString $Condition.implementation.name) -or -not (Test-NonEmptyString $Condition.implementation.version)) { return $false }
    if (-not (Test-NonEmptyString $Condition.architecture) -or $Condition.options -isnot [array]) { return $false }
    return @($Condition.options | Where-Object { -not (Test-NonEmptyString $_) }).Count -eq 0 -and @($Condition.options | Select-Object -Unique).Count -eq @($Condition.options).Count
}
function Test-FindingItem {
    param($Item, [switch]$Simd)
    $allowed = @("detected", "not_detected", "not_checked", "unknown", "not_applicable")
    if (-not (Test-JsonObject $Item) -or $allowed -notcontains $Item.result) { return $false }
    $itemNames = @($Item.PSObject.Properties.Name | Sort-Object) -join ","
    if ($Simd) {
        if ($itemNames -ne "isa,result") { return $false }
        if ($Item.isa -isnot [array] -or @($Item.isa | Where-Object { -not (Test-NonEmptyString $_) }).Count -ne 0) { return $false }
        if (@($Item.isa | Select-Object -Unique).Count -ne @($Item.isa).Count) { return $false }
        return (($Item.result -eq "detected") -eq (@($Item.isa).Count -gt 0))
    }
    return $itemNames -eq "result"
}
function Test-AnalysisFindings {
    param($Findings, [string[]]$ExpectedNames)
    if (-not (Test-JsonObject $Findings)) { return $false }
    $names = @($Findings.PSObject.Properties.Name | Sort-Object)
    if (($names -join ",") -ne ((@($ExpectedNames | Sort-Object)) -join ",")) { return $false }
    foreach ($name in @($ExpectedNames | Where-Object { $_ -ne "simd" })) {
        if (-not (Test-FindingItem $Findings.$name)) { return $false }
    }
    return Test-FindingItem $Findings.simd -Simd
}
function Test-ManifestEntry {
    param($Entry, [string[]]$ExpectedNames)
    if (-not (Test-JsonObject $Entry) -or -not (Test-NonEmptyString $Entry.artifact_id)) { return $false }
    if (-not (Test-AnalysisTimestamp $Entry.analyzed_at)) { return $false }
    if ($Entry.applies_to -isnot [array] -or (@($Entry.applies_to | Sort-Object) -join ",") -ne (@($ExpectedNames | Sort-Object) -join ",")) { return $false }
    if (-not (Test-AnalysisCondition $Entry.condition) -or -not (Test-AnalysisFindings $Entry.findings $ExpectedNames)) { return $false }
    if ($Entry.generation_commands -isnot [array] -or @($Entry.generation_commands).Count -eq 0) { return $false }
    if (@($Entry.generation_commands | Where-Object { -not (Test-NonEmptyString $_) }).Count -ne 0) { return $false }
    if ($Entry.evidence -isnot [array] -or @($Entry.evidence).Count -eq 0) { return $false }
    return @($Entry.evidence | Where-Object {
        -not (Test-JsonObject $_) -or
        (@($_.PSObject.Properties.Name | Sort-Object) -join ",") -ne "path,type" -or
        -not (Test-NonEmptyString $_.type) -or
        -not (Test-NonEmptyString $_.path)
    }).Count -eq 0
}
function Test-ManifestDocument {
    param($Document)
    if (-not (Test-JsonObject $Document)) { return $false }
    if ((@($Document.PSObject.Properties.Name | Sort-Object) -join ",") -ne "analysis_id,generated_at,languages,schema_version") { return $false }
    if ($Document.schema_version -ne "1.0" -or -not (Test-NonEmptyString $Document.analysis_id) -or -not (Test-AnalysisTimestamp $Document.generated_at)) { return $false }
    if (-not (Test-JsonObject $Document.languages)) { return $false }
    if ((@($Document.languages.PSObject.Properties.Name | Sort-Object) -join ",") -ne "c,javascript,python") { return $false }
    $expectedByLanguage = @{
        c = @("inlining", "vectorization", "simd")
        python = @("inlining", "vectorization", "simd")
        javascript = @("jit", "inlining", "vectorization", "simd")
    }
    foreach ($language in @("c", "python", "javascript")) {
        if (-not (Test-ManifestEntry $Document.languages.$language $expectedByLanguage[$language])) { return $false }
    }
    return $true
}

$scriptDir = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$sourcePath = (Resolve-Path (Join-Path $scriptDir "main.c")).Path
$manifestPath = if ([string]::IsNullOrWhiteSpace($AnalysisManifestPath)) { Join-Path $projectRoot "artifacts\function-call-analysis\manifest.json" } else { $AnalysisManifestPath }
$exePath = Join-Path ([System.IO.Path]::GetTempPath()) ("langbench-function-call-{0}.exe" -f [guid]::NewGuid().ToString("N"))
$analysisPath = Join-Path ([System.IO.Path]::GetTempPath()) ("langbench-function-call-analysis-{0}.json" -f [guid]::NewGuid().ToString("N"))
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
$currentCondition = [ordered]@{
    source_sha256 = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    implementation = [ordered]@{ name = "GCC"; version = $compilerVersion }
    architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
    options = $optimizationArgs
}
try {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not (Test-ManifestDocument $manifest)) { throw "manifest document is invalid" }
    $entry = $manifest.languages.c
    $entryAnalyzedAt = if ($entry.analyzed_at -is [datetime]) { $entry.analyzed_at.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") } else { $entry.analyzed_at }
    $mismatches = @(Compare-AnalysisCondition $entry.condition $currentCondition)
    $matched = $mismatches.Count -eq 0
    $provenance = [ordered]@{
        status = if ($matched) { "matched" } else { "mismatched" }
        artifact_id = $entry.artifact_id
        analyzed_at = $entryAnalyzedAt
        applies_to = @($entry.applies_to)
        analysis = $entry.condition
        artifact_findings = $entry.findings
        current = $currentCondition
        matched = $matched
        mismatches = $mismatches
    }
    $manifestFailure = $null
} catch {
    $manifestFailure = if (Test-Path -LiteralPath $manifestPath) { "manifest_invalid" } else { "manifest_unavailable" }
    $provenance = [ordered]@{
        status = "unavailable"
        artifact_id = $null
        analyzed_at = $null
        applies_to = @("inlining", "vectorization", "simd")
        analysis = $null
        artifact_findings = $null
        current = $currentCondition
        matched = $false
        mismatches = @($manifestFailure)
    }
}
$fallbackResult = if ($provenance.status -eq "unavailable") { "unknown" } else { "not_checked" }
$activeFindings = if ($provenance.status -eq "matched") {
    $entry.findings
} else {
    [ordered]@{
        inlining = [ordered]@{ result = $fallbackResult }
        vectorization = [ordered]@{ result = $fallbackResult }
        simd = [ordered]@{ result = $fallbackResult; isa = @() }
    }
}
$notes = [object[]]$(if ($provenance.status -eq "matched") {
    "Optimization findings were loaded from the matching GCC analysis manifest entry."
} elseif ($provenance.status -eq "mismatched") {
    "Saved C analysis was not applied because these conditions differed: $($provenance.mismatches -join ', ')."
} else {
    "Saved C analysis could not be loaded or was invalid; its findings are unknown."
})
$analysisEvidence = [object[]]@()
if ($provenance.status -eq "matched") { $analysisEvidence = [object[]]@($entry.evidence) }
$optimizationAnalysis = [ordered]@{
    implementation = $currentCondition.implementation
    provenance = $provenance
    jit = [ordered]@{ applicable = $false; result = "not_applicable" }
    inlining = $activeFindings.inlining
    vectorization = $activeFindings.vectorization
    simd = $activeFindings.simd
    other_optimizations = @()
    evidence = $analysisEvidence
    notes = $notes
}
$optimizationAnalysisJson = $optimizationAnalysis | ConvertTo-Json -Depth 10 -Compress

if ($ResolveAnalysisOnly) {
    Write-Output $optimizationAnalysisJson
    exit 0
}

[System.IO.File]::WriteAllText($analysisPath, $optimizationAnalysisJson, [System.Text.UTF8Encoding]::new($false))

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
& gcc @gccArgs
$compileExitCode = $LASTEXITCODE
$stopwatch.Stop()
$compileMs = [Math]::Round($stopwatch.Elapsed.TotalMilliseconds, 3)

if ($compileExitCode -ne 0) {
    Remove-Item -LiteralPath $exePath, $analysisPath -Force -ErrorAction SilentlyContinue
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=gcc failed with exit code $compileExitCode")
    exit $compileExitCode
}

Push-Location $projectRoot
try {
    $benchmarkArgs = @($compileMs, $compilerVersion, $compileCommand, $sourcePath, $analysisPath)
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
    Remove-Item -LiteralPath $exePath, $analysisPath -Force -ErrorAction SilentlyContinue
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=benchmark process failed with exit code $benchmarkExitCode")
    exit $benchmarkExitCode
}

if (-not (Test-Path -LiteralPath $resultPath)) {
    Remove-Item -LiteralPath $exePath, $analysisPath -Force -ErrorAction SilentlyContinue
    [Console]::Error.WriteLine("status=error")
    [Console]::Error.WriteLine("message=result JSON was not created")
    exit 1
}

$benchmarkOutput | ForEach-Object { Write-Host $_ }
Write-Host "compile_ms=$compileMs"
Remove-Item -LiteralPath $exePath, $analysisPath -Force -ErrorAction SilentlyContinue
exit 0
