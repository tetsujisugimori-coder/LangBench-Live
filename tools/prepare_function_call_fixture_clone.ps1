param(
    [Parameter(Mandatory = $true)][string]$SourceRepository,
    [Parameter(Mandatory = $true)][string]$Destination,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceSha
)

$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceRepository).Path
if (Test-Path -LiteralPath $Destination) { throw 'fixture destination already exists' }
& git clone --quiet --no-local --no-checkout $source $Destination
if ($LASTEXITCODE -ne 0) { throw 'failed to create independent fixture clone' }
& git -C $Destination show-ref --verify --quiet refs/heads/main
if ($LASTEXITCODE -eq 0) {
    & git -C $Destination switch --quiet main
} else {
    & git -C $Destination switch --quiet -c main $SourceSha
}
if ($LASTEXITCODE -ne 0) { throw 'failed to select fixture main branch' }
if ((& git -C $Destination rev-parse HEAD).Trim() -ne $SourceSha) { throw 'fixture clone SHA differs' }
$branch = @(& git -C $Destination symbolic-ref --quiet --short HEAD)
if ($LASTEXITCODE -ne 0 -or $branch.Count -ne 1 -or $branch[0] -ne 'main') { throw 'fixture clone is not on main' }
if ((& git -C $Destination remote get-url origin).Trim() -cne $source) { throw 'fixture clone origin differs' }
