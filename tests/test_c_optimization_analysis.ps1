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
        @{ Path = (Join-Path $tempRoot "missing.json"); Reason = "manifest_unavailable" },
        @{ Path = $syntaxPath; Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "condition-missing" { param($d) $d.languages.c.PSObject.Properties.Remove("condition") }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "findings-missing" { param($d) $d.languages.c.PSObject.Properties.Remove("findings") }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "implementation-invalid" { param($d) $d.languages.c.condition.implementation = "GCC" }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "evidence-invalid" { param($d) $d.languages.c.evidence = "assembly.txt" }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "schema-version" { param($d) $d.schema_version = "2.0" }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "analysis-id-missing" { param($d) $d.PSObject.Properties.Remove("analysis_id") }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "generated-at-invalid" { param($d) $d.generated_at = "not-a-timestamp" }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "languages-array" { param($d) $d.languages = @() }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "languages-null" { param($d) $d.languages = $null }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "sibling-missing" { param($d) $d.languages.PSObject.Properties.Remove("python") }); Reason = "manifest_invalid" },
        @{ Path = (Write-ManifestVariant "unknown-root" { param($d) $d | Add-Member -NotePropertyName unexpected -NotePropertyValue $true }); Reason = "manifest_invalid" }
    )
    foreach ($case in $cases) {
        $analysis = Resolve-Analysis $case.Path
        Assert-True ($analysis.provenance.status -eq "unavailable") "invalid C manifest was not unavailable: $($case.Path)"
        Assert-True (-not $analysis.provenance.matched) "invalid C manifest was marked matched: $($case.Path)"
        Assert-True (@($analysis.provenance.mismatches).Count -eq 1 -and $analysis.provenance.mismatches[0] -eq $case.Reason) "invalid C manifest reason differed: $($case.Path)"
        foreach ($field in @("artifact_id", "analyzed_at", "analysis", "artifact_findings")) {
            Assert-True ($null -eq $analysis.provenance.$field) "invalid C manifest exposed $field`: $($case.Path)"
        }
        Assert-True ($analysis.inlining.result -eq "unknown") "invalid C manifest did not produce unknown: $($case.Path)"
        Assert-True ($analysis.vectorization.result -eq "unknown") "invalid C manifest did not produce unknown vectorization: $($case.Path)"
        Assert-True ($analysis.simd.result -eq "unknown" -and @($analysis.simd.isa).Count -eq 0) "invalid C manifest did not clear SIMD: $($case.Path)"
        Assert-True (@($analysis.evidence).Count -eq 0) "invalid C manifest exposed evidence: $($case.Path)"
    }
    Write-Host "tests=14 passed=14"
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
