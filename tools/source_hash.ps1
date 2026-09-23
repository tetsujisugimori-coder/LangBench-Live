function Get-CanonicalSourceHash {
    param([Parameter(Mandatory = $true)][string]$Path)

    # Git can leave CRLF in an unchanged Windows worktree file after eol=lf is added.
    # Hash its actual bytes with only CRLF pairs converted to LF.
    [byte[]]$source = [System.IO.File]::ReadAllBytes($Path)
    [byte[]]$canonical = [System.Array]::CreateInstance([byte], $source.Length)
    $length = 0
    for ($index = 0; $index -lt $source.Length; $index++) {
        if ($source[$index] -eq 13 -and $index + 1 -lt $source.Length -and $source[$index + 1] -eq 10) {
            continue
        }
        $canonical[$length] = $source[$index]
        $length++
    }

    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha256.ComputeHash($canonical, 0, $length)
        return [System.BitConverter]::ToString($digest).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha256.Dispose()
    }
}
