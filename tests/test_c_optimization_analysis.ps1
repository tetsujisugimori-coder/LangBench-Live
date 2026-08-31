$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runner = Join-Path $projectRoot "benchmarks\function_call_numeric_sum\c\run_c.ps1"
$manifestPath = Join-Path $projectRoot "artifacts\function-call-analysis\manifest.json"
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("langbench-c-analysis-test-" + [guid]::NewGuid().ToString("N"))
[System.IO.Directory]::CreateDirectory($tempRoot) | Out-Null

function Assert-True { param([bool]$Condition, [string]$Message) if (-not $Condition) { throw $Message } }
function Resolve-Analysis {
    param([string]$Path)
    $output = @(& $runner -AnalysisManifestPath $Path -ResolveAnalysisOnly)
    if ($LASTEXITCODE -ne 0) { throw "C analysis resolution failed for $Path" }
    return ($output[-1] | ConvertFrom-Json)
}
function Write-ManifestVariant {
    param([string]$Name, [scriptblock]$Mutate)
    $document = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    & $Mutate $document
    $path = Join-Path $tempRoot "$Name.json"
    [System.IO.File]::WriteAllText($path, ($document | ConvertTo-Json -Depth 15), [System.Text.UTF8Encoding]::new($false))
    return $path
}

try {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $matched = Resolve-Analysis $manifestPath
    Assert-True ($matched.provenance.status -eq "matched") "valid C manifest did not match"
    Assert-True (($matched.simd | ConvertTo-Json -Compress) -eq ($manifest.languages.c.findings.simd | ConvertTo-Json -Compress)) "C SIMD finding was not loaded from the manifest"

    $syntaxPath = Join-Path $tempRoot "syntax.json"
    [System.IO.File]::WriteAllText($syntaxPath, "{", [System.Text.UTF8Encoding]::new($false))
    $cases = @(
        (Join-Path $tempRoot "missing.json"),
        $syntaxPath,
        (Write-ManifestVariant "condition-missing" { param($d) $d.languages.c.PSObject.Properties.Remove("condition") }),
        (Write-ManifestVariant "findings-missing" { param($d) $d.languages.c.PSObject.Properties.Remove("findings") }),
        (Write-ManifestVariant "implementation-invalid" { param($d) $d.languages.c.condition.implementation = "GCC" }),
        (Write-ManifestVariant "evidence-invalid" { param($d) $d.languages.c.evidence = "assembly.txt" })
    )
    foreach ($path in $cases) {
        $analysis = Resolve-Analysis $path
        Assert-True ($analysis.provenance.status -eq "unavailable") "invalid C manifest was not unavailable: $path"
        Assert-True ($null -eq $analysis.provenance.artifact_findings) "invalid C manifest exposed findings: $path"
        Assert-True ($analysis.inlining.result -eq "unknown") "invalid C manifest did not produce unknown: $path"
    }
    Write-Host "tests=7 passed=7"
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
