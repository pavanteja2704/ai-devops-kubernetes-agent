$ErrorActionPreference = "Stop"

$script = Get-Content -LiteralPath (Join-Path $PSScriptRoot "deploy.ps1") -Raw
$definitions = foreach ($name in @("Test-WorkloadIdentityPool", "Get-NodePoolMetadataMode")) {
    $match = [regex]::Match($script, '(?s)function ' + $name + ' \{.*?\r?\n\}')
    if (-not $match.Success) {
        throw "Function $name was not found in deploy.ps1."
    }
    $match.Value
}
Invoke-Expression ($definitions -join "`n")

if (-not (Test-WorkloadIdentityPool "ai-4-509612.svc.id.goog" "ai-4-509612")) {
    throw "Expected the project Workload Identity pool to be accepted."
}
if (Test-WorkloadIdentityPool "" "ai-4-509612") {
    throw "An empty Workload Identity pool must not be accepted."
}

$enabledPool = [pscustomobject]@{
    config = [pscustomobject]@{
        workloadMetadataConfig = [pscustomobject]@{ mode = "GKE_METADATA" }
    }
}
$missingPoolConfig = [pscustomobject]@{ config = $null }
if ((Get-NodePoolMetadataMode $enabledPool) -ne "GKE_METADATA") {
    throw "GKE_METADATA mode was not detected."
}
if ((Get-NodePoolMetadataMode $missingPoolConfig) -ne "") {
    throw "Missing node-pool metadata configuration was not detected."
}

Write-Output "Workload Identity detection validation: passed"
