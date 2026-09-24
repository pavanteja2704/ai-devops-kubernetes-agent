$ErrorActionPreference = "Stop"

$script = Get-Content -LiteralPath (Join-Path $PSScriptRoot "deploy.ps1") -Raw
$functionMatch = [regex]::Match(
    $script,
    '(?s)function Get-GkeLocationType \{.*?\r?\n\}'
)
if (-not $functionMatch.Success) {
    throw "Get-GkeLocationType was not found in deploy.ps1."
}

$functionDefinition = $functionMatch.Value
Invoke-Expression $functionDefinition

$cases = @(
    @{ Location = "us-central1-a"; Expected = "zone" },
    @{ Location = "us-central1"; Expected = "region" },
    @{ Location = "asia-south1-a"; Expected = "zone" },
    @{ Location = "asia-south1"; Expected = "region" }
)

foreach ($case in $cases) {
    $actual = Get-GkeLocationType $case.Location
    if ($actual -ne $case.Expected) {
        throw "Expected '$($case.Location)' to be classified as '$($case.Expected)', got '$actual'."
    }
}

Write-Output "GKE location validation: 4 passed"
