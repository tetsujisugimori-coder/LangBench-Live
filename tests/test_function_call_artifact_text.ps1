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
                    '\root\private\file.txt', '/srv/private/file.txt',
                    '/tmp', '/etc', '\secret', 'C:\', 'D:/',
                    'file:///C:/Users/alice/private', 'file:///home/alice/private',
                    '/ユーザー/秘密')) {
    $safe = Protect-ArtifactText $value
    if ($safe -ne '<absolute-path>') { throw "absolute path was not fully sanitized: $value" }
}
$mixed = Protect-ArtifactText 'safe reason: exit 23; D:/a/private/file.txt; safe tail'
if ($mixed -notmatch 'safe reason: exit 23' -or $mixed -notmatch 'safe tail' -or $mixed -match 'private') {
    throw 'safe diagnostic text was lost while sanitizing a path'
}
foreach ($value in @('https://example.com/srv/private', 'split(/\s+/)',
                     'cl /O2 /EHsc main.c', 'option /quiet',
                     '<checkout>/tools/trace.js', '<analysis-package>/main.s',
                     '<shared-repository>/results')) {
    if ((Protect-ArtifactText $value) -cne $value) { throw "safe diagnostic changed: $value" }
}
foreach ($value in @('cwd = /secret/', 'path = /tmp/', 'return /etc/',
                     'trace (/home/)', 'cwd = /quiet',
                     'stderr >/tmp/private.log', 'path:/home/alice/file',
                     'tag=<note>/srv/private')) {
    if ((Protect-ArtifactText $value) -notmatch '<absolute-path>') { throw "unsafe diagnostic was retained: $value" }
}
foreach ($value in @('return /etc/gg;', 'return /etc/uv;', 'if (/home/gg)',
                     'const r = /foo/;', 'const r = /foo/', 'return /foo/g')) {
    if ((Protect-ArtifactText $value) -notmatch '<absolute-path>') { throw "trace path was retained: $value" }
}
Write-Host 'tests=36 passed=36'
