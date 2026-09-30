$ErrorActionPreference = 'Stop'
$generator = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'tools/generate_function_call_analysis.ps1'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($generator, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'generator parse failed' }
$definition = $ast.Find({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Protect-ArtifactText' }, $true)
if ($null -eq $definition) { throw 'sanitizer function missing' }
Invoke-Expression $definition.Extent.Text
$artifactDir = 'D:\a\analysis'
$projectRoot = 'D:\a\checkout'
$sharedRoot = 'C:\Users\fixture\shared'
foreach ($value in @('D:/a/private/file.txt', 'D:\a\private\file.txt',
                    '\\server\share\private\file.txt', '\\?\C:\private\file.txt',
                    '\root\private\file.txt', '/srv/private/file.txt')) {
    $safe = Protect-ArtifactText $value
    if ($safe -match 'private' -or $safe -notmatch '<absolute-path>') { throw 'absolute path was not sanitized' }
}
$mixed = Protect-ArtifactText 'safe reason: exit 23; D:/a/private/file.txt; safe tail'
if ($mixed -notmatch 'safe reason: exit 23' -or $mixed -notmatch 'safe tail' -or $mixed -match 'private') {
    throw 'safe diagnostic text was lost while sanitizing a path'
}
Write-Host 'tests=7 passed=7'
