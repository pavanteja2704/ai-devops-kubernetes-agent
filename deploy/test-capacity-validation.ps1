$ErrorActionPreference = "Stop"

$script = Get-Content -LiteralPath (Join-Path $PSScriptRoot "deploy.ps1") -Raw
$functionMatch = [regex]::Match(
    $script,
    '(?s)function Test-AllocatableCapacity \{.*?\r?\n\}'
)
if (-not $functionMatch.Success) {
    throw "Test-AllocatableCapacity was not found in deploy.ps1."
}

Invoke-Expression $functionMatch.Value

if (-not (Test-AllocatableCapacity 3920 13273)) {
    throw "A healthy 3920m CPU and 13273Mi memory node should pass."
}
if (Test-AllocatableCapacity 3499 13273) {
    throw "A cluster below the CPU minimum should fail."
}
if (Test-AllocatableCapacity 3920 8191) {
    throw "A cluster below the memory minimum should fail."
}

Write-Output "Allocatable capacity validation: pass/fail cases passed"
