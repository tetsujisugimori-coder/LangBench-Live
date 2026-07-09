$ErrorActionPreference = "Stop"

function Format-CommandPart {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value -match '[\s"]') {
        return '"' + $Value.Replace('"', '\"') + '"'
    }
    return $Value
}

$scriptDir = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$sourcePath = (Resolve-Path (Join-Path $scriptDir "main.c")).Path
$exePath = Join-Path $scriptDir "main.exe"
$resultsDir = Join-Path $projectRoot "results"
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
    & $exePath $compileMs $compilerVersion $compileCommand $sourcePath
    $runExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

exit $runExitCode
