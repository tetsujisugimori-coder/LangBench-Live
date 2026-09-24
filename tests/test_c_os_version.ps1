$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$harness = Join-Path $PSScriptRoot "c_os_version_harness.c"
$executable = Join-Path ([System.IO.Path]::GetTempPath()) ("langbench-os-version-{0}.exe" -f [guid]::NewGuid().ToString("N"))
try {
    & gcc $harness -O2 -std=c11 -Wall -Wextra -o $executable
    if ($LASTEXITCODE -ne 0) { throw "OS version harness compilation failed" }
    $output = @(& $executable)
    if ($LASTEXITCODE -ne 0) { throw "OS version harness failed with exit code $LASTEXITCODE" }
    $actual = ($output | Where-Object { $_ -match '^os_version=' }) -replace '^os_version=', ''
    $expected = (& node -p "require('os').release()").Trim()
    if ($LASTEXITCODE -ne 0 -or $actual -ne $expected) { throw "C OS version $actual differs from Node OS release $expected" }
    Write-Host "tests=5 passed=5 os_version=$actual"
} finally {
    Remove-Item -LiteralPath $executable -Force -ErrorAction SilentlyContinue
}
