$ErrorActionPreference = "Stop"

$script = Get-Content -LiteralPath (Join-Path $PSScriptRoot "deploy.ps1") -Raw
$functionDefinitions = foreach ($name in @("Get-NodePoolMetadataMode", "Get-NodePoolStatus")) {
    $match = [regex]::Match($script, '(?s)function ' + $name + ' \{.*?\r?\n\}')
    if (-not $match.Success) {
        throw "Function $name was not found."
    }
    $match.Value
}
Invoke-Expression ($functionDefinitions -join "`n")

$configured = [pscustomobject]@{
    name = "ai-devops-agent-pool"
    status = "RUNNING"
    config = [pscustomobject]@{
        workloadMetadataConfig = [pscustomobject]@{ mode = "GKE_METADATA" }
    }
}
$needsUpdate = [pscustomobject]@{
    name = "ai-devops-agent-pool"
    status = "RUNNING"
    config = [pscustomobject]@{
        workloadMetadataConfig = [pscustomobject]@{ mode = "GCE_METADATA" }
    }
}
$unrelated = [pscustomobject]@{
    name = "default-pool"
    status = "RUNNING"
    config = [pscustomobject]@{
        workloadMetadataConfig = [pscustomobject]@{ mode = "GCE_METADATA" }
    }
}

$allPools = @($configured, $unrelated)
$agentName = "ai-devops-agent-pool"
$matches = @($allPools | Where-Object { $_.name -eq $agentName })
if ($matches.Count -ne 1) {
    throw "Configured agent node pool did not resolve to exactly one pool."
}
if ((Get-NodePoolMetadataMode $configured) -ne "GKE_METADATA") {
    throw "Already-compliant agent node pool was not detected."
}
if ((Get-NodePoolMetadataMode $needsUpdate) -eq "GKE_METADATA") {
    throw "Noncompliant test node pool unexpectedly appeared compliant."
}
if ((Get-NodePoolStatus $configured) -ne "RUNNING") {
    throw "Running agent node pool was not detected."
}

if ($script -notmatch 'node-pools",\s*"update",\s*\$AgentNodePool') {
    throw "The update command is not constrained to AgentNodePool."
}
if ($script -match 'node-pools",\s*"update",\s*\$(?!AgentNodePool)') {
    throw "An unrelated node-pool update target exists."
}
if ($script -match 'node-pools",\s*"create"') {
    throw "A node-pool creation command exists."
}

Write-Output "Node-pool mutation safety validation: passed"
