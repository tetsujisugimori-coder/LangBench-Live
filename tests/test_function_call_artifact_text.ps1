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
                     '<shared-repository>/results', 'https:\/\/example.com\/srv\/private')) {
    if ((Protect-ArtifactText $value) -cne $value) { throw "safe diagnostic changed: $value" }
}
foreach ($value in @('cwd = /secret/', 'path = /tmp/', 'return /etc/',
                     'trace (/home/)', 'cwd = /quiet',
                     'stderr >/tmp/private.log', 'path:/home/alice/file',
                     'tag=<note>/srv/private', '\/home\/alice', '\/tmp',
                     'stderr >\/tmp\/private.log', 'path:\/home\/alice')) {
    if ((Protect-ArtifactText $value) -notmatch '<absolute-path>') { throw "unsafe diagnostic was retained: $value" }
}
foreach ($value in @('return /etc/gg;', 'return /etc/uv;', 'if (/home/gg)',
                     'const r = /foo/;', 'const r = /foo/', 'return /foo/g')) {
    if ((Protect-ArtifactText $value) -notmatch '<absolute-path>') { throw "trace path was retained: $value" }
}
$json = '{"cwd":"\/\u0068ome\/alice","nested":[{"path":"C:\\Users\\alice\\private"},{"url":"https:\/\/example.com\/srv\/private"}]}'
$cleaned = (Protect-ArtifactText $json) | ConvertFrom-Json -AsHashtable
if ($cleaned.cwd -ne '<redacted-absolute-path>' -or $cleaned.nested[0].path -ne '<redacted-absolute-path>' -or
    $cleaned.nested[1].url -ne 'https://example.com/srv/private') { throw 'JSON decoded path was not safely redacted' }
$credentialJson = '{"password":"dummy-pass","nested":{"ToKeN":"dummy-token","reason":"safe failure","exit_code":23},"events":[{"\u0073ecret":{"child":"dummy-child","trace":["prior trace"]},"AUTHORIZATION":"Basic ZHVtbXk="}],"authorization":["dummy-array",{"child":"dummy-child-2"}],"option":"cl /O2 /EHsc main.c","trace":"safe trace"}'
$credentialText = Protect-ArtifactText $credentialJson
$credentialFields = $credentialText | ConvertFrom-Json -AsHashtable
if ($credentialFields.password -ne '<redacted-credential>' -or
    $credentialFields.nested.ToKeN -ne '<redacted-credential>' -or
    $credentialFields.events[0].secret -ne '<redacted-credential>' -or
    $credentialFields.events[0].AUTHORIZATION -ne '<redacted-credential>' -or
    $credentialFields.authorization -ne '<redacted-credential>' -or
    $credentialFields.nested.reason -ne 'safe failure' -or
    $credentialFields.nested.exit_code -ne 23 -or
    $credentialFields.option -ne 'cl /O2 /EHsc main.c' -or
    $credentialFields.trace -ne 'safe trace') { throw 'JSON credential field redaction lost evidence' }
if ($credentialText -match 'dummy-|ZHVtbXk=' -or (Protect-ArtifactText $credentialText) -cne $credentialText) {
    throw 'JSON credential field was retained or redaction is not stable'
}
foreach ($value in @('{"cwd":"/home/alice","cwd":"safe"}',
                     '{"cwd":"safe","cwd":"/home/alice"}',
                     '{"nested":{"cwd":"\/\u0068ome\/alice","cwd":"safe"}}',
                     '{"credential":"ghp_abcdefghijklmnop","credential":"safe"}',
                     '{"CWD":"/tmp","cwd":"safe"}')) {
    if ((Protect-ArtifactText $value) -ne '<invalid-json-duplicate-keys>') {
        throw 'duplicate JSON key was not rejected'
    }
}
$collision = '{"/home/alice/a":"first","/home/bob/b":"second","/tmp":"third"}'
$collisionCleaned = (Protect-ArtifactText $collision) | ConvertFrom-Json -AsHashtable
if ($collisionCleaned.Count -ne 3 -or
    $collisionCleaned['<redacted-absolute-path>'] -ne 'first' -or
    $collisionCleaned['<redacted-absolute-path>-1'] -ne 'second' -or
    $collisionCleaned['<redacted-absolute-path>-2'] -ne 'third') { throw 'path key collision lost evidence' }
$nestedCollision = '{"entries":[{"/home/alice/a":"first","/home/bob/b":"second"}]}'
$nestedCleaned = (Protect-ArtifactText $nestedCollision) | ConvertFrom-Json -AsHashtable
if ($nestedCleaned.entries[0].Count -ne 2 -or
    $nestedCleaned.entries[0]['<redacted-absolute-path>'] -ne 'first' -or
    $nestedCleaned.entries[0]['<redacted-absolute-path>-1'] -ne 'second') { throw 'nested collision lost evidence' }
$credentialCollision = '{"ghp_abcdefghijklmnop":"first","ghp_qrstuvwxyzabcdefgh":"second"}'
$credentialCleaned = (Protect-ArtifactText $credentialCollision) | ConvertFrom-Json -AsHashtable
if ($credentialCleaned.Count -ne 2 -or
    $credentialCleaned['<redacted-credential>'] -ne 'first' -or
    $credentialCleaned['<redacted-credential>-1'] -ne 'second') { throw 'credential key collision lost evidence' }
Write-Host 'tests=51 passed=51'
