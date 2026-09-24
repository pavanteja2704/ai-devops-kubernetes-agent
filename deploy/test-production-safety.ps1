$ErrorActionPreference = "Stop"

$deployPath = Join-Path $PSScriptRoot "deploy.ps1"
$inputPath = Join-Path $PSScriptRoot "inputs.yaml"
$deployScript = Get-Content -LiteralPath $deployPath -Raw
$inputText = Get-Content -LiteralPath $inputPath -Raw

foreach ($pattern in @(
    '(?m)^project_id:\s*"[^"]+"\s*$',
    '(?m)^\s+name:\s*"[^"]+"\s*$',
    '(?m)^\s+location:\s*"[^"]+"\s*$',
    '(?m)^\s+namespace:\s*"[^"]+"\s*$',
    '(?m)^\s+node_pool:\s*"[^"]+"\s*$'
)) {
    if ($inputText -notmatch $pattern) {
        throw "Required inputs.yaml field was not found: $pattern"
    }
}

foreach ($required in @("__AGENT_NAMESPACE__", "__AGENT_NODE_POOL__")) {
    foreach ($manifest in @("deployment.yaml", "frontend-deployment.yaml")) {
        $content = Get-Content -LiteralPath (Join-Path $PSScriptRoot "..\kubernetes\$manifest") -Raw
        if ($content -notmatch [regex]::Escape($required)) {
            throw "$manifest does not contain scheduling placeholder $required."
        }
    }
}
$namespace = ([regex]::Match($inputText, '(?m)^\s+namespace:\s*"([^"]+)"\s*$')).Groups[1].Value
$nodePool = ([regex]::Match($inputText, '(?m)^\s+node_pool:\s*"([^"]+)"\s*$')).Groups[1].Value
foreach ($manifest in @("deployment.yaml", "frontend-deployment.yaml")) {
    $rendered = Get-Content -LiteralPath (Join-Path $PSScriptRoot "..\kubernetes\$manifest") -Raw
    $rendered = $rendered.Replace("__AGENT_NAMESPACE__", $namespace).Replace("__AGENT_NODE_POOL__", $nodePool)
    if ($rendered -notmatch "namespace:\s*$([regex]::Escape($namespace))") {
        throw "$manifest does not render the configured namespace."
    }
    if ($rendered -notmatch "cloud\.google\.com/gke-nodepool:\s*$([regex]::Escape($nodePool))") {
        throw "$manifest does not render the configured node-pool scheduling constraint."
    }
}

if ($deployScript -notmatch 'Configured agent node pool.*not found') {
    throw "deploy.ps1 does not clearly fail when the configured node pool is missing."
}
if ($deployScript -notmatch 'node-pools",\s*"update",\s*\$AgentNodePool') {
    throw "deploy.ps1 does not update the configured agent node pool explicitly."
}
if ($deployScript -match 'node-pools",\s*"update",\s*\$(?!AgentNodePool)') {
    throw "deploy.ps1 contains a node-pool update target that is not AgentNodePool."
}
if ($deployScript -match 'node-pools",\s*"create"') {
    throw "deploy.ps1 contains a node-pool creation command."
}
if ($deployScript -notmatch 'Only the configured agent node pool may be modified') {
    throw "deploy.ps1 is missing the explicit node-pool modification safety message."
}

Write-Output "Production deployment safety validation: passed"
