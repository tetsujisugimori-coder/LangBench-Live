param(
    [ValidateSet("none", "O0", "O1", "O2", "O3")]
    [string]$OptimizationLevel = "none"
)

$ErrorActionPreference = "Stop"

function Format-CommandPart {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ($Value -match '[\s"]') {
        return '"' + $Value.Replace('"', '\"') + '"'
    }

    return $Value
}

function Set-JsonProperty {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Object,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        $Value
    )

    if ($Object.PSObject.Properties.Name -contains $Name) {
        $Object.$Name = $Value
    } else {
        $Object | Add-Member -MemberType NoteProperty -Name $Name -Value $Value
    }
}

$scriptDir = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$sourcePath = (Resolve-Path (Join-Path $scriptDir "main.c")).Path
$exePath = Join-Path $scriptDir "main.exe"
$resultJsonPath = Join-Path $projectRoot "results\jit_function_c_result.json"

$optimizationArg = if ($OptimizationLevel -eq "none") { $null } else { "-$OptimizationLevel" }

$gccArgs = @()
if ($null -ne $optimizationArg) {
    $gccArgs += $optimizationArg
}
$gccArgs += $sourcePath
$gccArgs += "-o"
$gccArgs += $exePath

$compileCommand = "gcc " + (($gccArgs | ForEach-Object { Format-CommandPart $_ }) -join " ")

Write-Host "compile_command=$compileCommand"
Start-Sleep -Milliseconds 250
$compileExitCode = 1
$lastCompileOutput = @()
for ($attempt = 1; $attempt -le 5; $attempt += 1) {
    $compileOutput = & gcc @gccArgs 2>&1
    $compileExitCode = $LASTEXITCODE
    if ($compileExitCode -eq 0) {
        break
    }

    $lastCompileOutput = $compileOutput
    if ($attempt -lt 5) {
        Start-Sleep -Milliseconds (500 * $attempt)
    }
}

if ($compileExitCode -ne 0) {
    $lastCompileOutput | ForEach-Object { Write-Error $_ }
    Write-Error "gcc failed with exit code $compileExitCode"
    exit $compileExitCode
}

Write-Host "run_command=$exePath"
Push-Location $projectRoot
try {
    & $exePath
    $runExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($runExitCode -ne 0) {
    Write-Error "benchmark failed with exit code $runExitCode"
    exit $runExitCode
}

if (-not (Test-Path $resultJsonPath)) {
    Write-Error "result JSON was not created: $resultJsonPath"
    exit 1
}

$result = Get-Content -Raw -Encoding UTF8 $resultJsonPath | ConvertFrom-Json

if (-not $result.engine) {
    Set-JsonProperty -Object $result -Name "engine" -Value ([pscustomobject]@{})
}

if (-not $result.compilation) {
    Set-JsonProperty -Object $result -Name "compilation" -Value ([pscustomobject]@{})
}

$compilerVersion = "unknown"
if ($result.engine.PSObject.Properties.Name -contains "compiler_version") {
    $compilerVersion = $result.engine.compiler_version
} elseif ($result.compilation.PSObject.Properties.Name -contains "compiler_version") {
    $compilerVersion = $result.compilation.compiler_version
}

Set-JsonProperty -Object $result.engine -Name "compiler_name" -Value "gcc"
Set-JsonProperty -Object $result.engine -Name "compiler_version" -Value $compilerVersion
Set-JsonProperty -Object $result.engine -Name "compile_command" -Value $compileCommand
Set-JsonProperty -Object $result.engine -Name "optimization_level" -Value $OptimizationLevel

Set-JsonProperty -Object $result.compilation -Name "compiler_name" -Value "gcc"
Set-JsonProperty -Object $result.compilation -Name "compiler_version" -Value $compilerVersion
Set-JsonProperty -Object $result.compilation -Name "compile_command" -Value $compileCommand
Set-JsonProperty -Object $result.compilation -Name "optimization_level" -Value $OptimizationLevel

$jsonText = $result | ConvertTo-Json -Depth 24
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($resultJsonPath, $jsonText + [Environment]::NewLine, $utf8NoBom)

$verify = Get-Content -Raw -Encoding UTF8 $resultJsonPath | ConvertFrom-Json

if ($verify.engine.compile_command -ne $compileCommand -or
    $verify.compilation.compile_command -ne $compileCommand -or
    $verify.engine.optimization_level -ne $OptimizationLevel -or
    $verify.compilation.optimization_level -ne $OptimizationLevel) {
    Write-Error "failed to verify recorded compilation metadata"
    exit 1
}

Write-Host "recorded optimization_level=$($verify.compilation.optimization_level)"
Write-Host "recorded compile_command=$($verify.compilation.compile_command)"

exit 0
