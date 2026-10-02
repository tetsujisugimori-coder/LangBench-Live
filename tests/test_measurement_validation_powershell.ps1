$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$errors = $null
[void][Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $root 'tools/run_measurement_validation.ps1'), [ref]$null, [ref]$errors)
if (@($errors).Count) { throw ($errors | ForEach-Object Message | Out-String) }
Write-Host 'measurement validation PowerShell syntax: valid'
