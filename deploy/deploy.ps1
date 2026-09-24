[CmdletBinding()]
param(
    [string]$InputPath = (Join-Path $PSScriptRoot "inputs.yaml")
)

$ErrorActionPreference = "Stop"
$Namespace = "ai-devops-agent"
$Repository = "ai-devops-agent-repo"
$BackendName = "ai-devops-agent"
$FrontendName = "ai-devops-frontend"
$ServiceAccountName = "ai-devops-agent-sa"
$MinimumCpuMilli = 4000
$MinimumMemoryMi = 8192

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    $output = & $Command @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed: $($output -join [Environment]::NewLine)"
    }
    return @($output)
}

function Get-YamlScalar {
    param([string[]]$Lines, [string]$Pattern)
    $match = $Lines | Select-String -Pattern $Pattern | Select-Object -First 1
    if (-not $match) { throw "Missing required field in inputs.yaml: $Pattern" }
    $value = ([regex]::Match($match.Line, ':\s*["'']?([^"'']+)["'']?\s*$')).Groups[1].Value.Trim()
    if ([string]::IsNullOrWhiteSpace($value) -or $value -match "^YOUR_") {
        throw "Replace the placeholder value for $Pattern in $InputPath."
    }
    return $value
}

function Convert-ToMilliCpu {
    param([string]$Value)
    if ($Value -match '^(\d+)m$') { return [int]$Matches[1] }
    if ($Value -match '^(\d+)(\.\d+)?$') { return [int]([double]$Value * 1000) }
    return 0
}

function Convert-ToMi {
    param([string]$Value)
    if ($Value -match '^(\d+)Ki$') { return [int]([double]$Matches[1] / 1024) }
    if ($Value -match '^(\d+)Mi$') { return [int]$Matches[1] }
    if ($Value -match '^(\d+)Gi$') { return [int]$Matches[1] * 1024 }
    return 0
}

if (-not (Test-Path -LiteralPath $InputPath)) { throw "Input file not found: $InputPath" }
$inputLines = Get-Content -LiteralPath $InputPath
$ProjectId = Get-YamlScalar $inputLines "^project_id:"
$ClusterName = Get-YamlScalar $inputLines "^\s+name:"

foreach ($tool in @("gcloud", "kubectl", "docker")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is required and was not found on PATH." }
}
Invoke-Checked "docker" @("info") | Out-Null
Invoke-Checked "gcloud" @("auth", "list", "--filter=status:ACTIVE", "--format=value(account)") | Out-Null
Invoke-Checked "gcloud" @("config", "set", "project", $ProjectId) | Out-Null

$clusterRows = Invoke-Checked "gcloud" @("container", "clusters", "list", "--project=$ProjectId", "--filter=name=$ClusterName", "--format=csv[no-heading](name,location,locationType)")
if ($clusterRows.Count -ne 1) { throw "Expected exactly one existing GKE cluster named $ClusterName in project $ProjectId." }
$parts = $clusterRows[0].ToString().Split(",")
$ClusterLocation = $parts[1]
$LocationType = if ($parts[2] -match "REGIONAL") { "region" } else { "zone" }
$ArtifactRegion = if ($LocationType -eq "zone" -and $ClusterLocation -match "^(.*)-[a-z]$") { $Matches[1] } else { $ClusterLocation }

$locationFlag = if ($LocationType -eq "region") { "--region=$ClusterLocation" } else { "--zone=$ClusterLocation" }
Invoke-Checked "gcloud" @("container", "clusters", "get-credentials", $ClusterName, $locationFlag, "--project=$ProjectId") | Out-Null
Invoke-Checked "kubectl" @("cluster-info") | Out-Null
$nodeRows = Invoke-Checked "kubectl" @("get", "nodes", "-o", "jsonpath={range .items[*]}{.metadata.name}{','}{.status.allocatable.cpu}{','}{.status.allocatable.memory}{'\n'}{end}")
$totalCpu = 0
$totalMemory = 0
foreach ($row in $nodeRows) {
    if ([string]::IsNullOrWhiteSpace($row)) { continue }
    $node = $row.ToString().Split(",")
    if ($node.Count -lt 3) { continue }
    $cpu = Convert-ToMilliCpu $node[1]
    $memory = Convert-ToMi $node[2]
    $totalCpu += $cpu
    $totalMemory += $memory
    Write-Host "Node $($node[0]): allocatable CPU $($node[1]), memory $($node[2])"
}
if ($totalCpu -lt $MinimumCpuMilli -or $totalMemory -lt $MinimumMemoryMi) {
    throw "Cluster capacity is below the recommended minimum of 4 vCPU and 8 GiB allocatable memory. Detected approximately $totalCpu mCPU and $totalMemory MiB. Resize the cluster manually; deploy.ps1 will not resize or recreate node pools."
}

Invoke-Checked "gcloud" @("services", "enable", "container.googleapis.com", "artifactregistry.googleapis.com", "aiplatform.googleapis.com", "--project=$ProjectId") | Out-Null
$repoCheck = & gcloud artifacts repositories describe $Repository "--location=$ArtifactRegion" "--project=$ProjectId" 2>&1
if ($LASTEXITCODE -ne 0) {
    Invoke-Checked "gcloud" @("artifacts", "repositories", "create", $Repository, "--repository-format=docker", "--location=$ArtifactRegion", "--project=$ProjectId") | Out-Null
}
Invoke-Checked "gcloud" @("auth", "configure-docker", "$ArtifactRegion-docker.pkg.dev", "--quiet") | Out-Null

$registry = "$ArtifactRegion-docker.pkg.dev/$ProjectId/$Repository"
$backendImage = "$registry/$BackendName`:latest"
$frontendImage = "$registry/$FrontendName`:latest"
Invoke-Checked "docker" @("build", "-t", $backendImage, ".") | Out-Null
Invoke-Checked "docker" @("build", "-t", $frontendImage, "frontend") | Out-Null
Invoke-Checked "docker" @("push", $backendImage) | Out-Null
Invoke-Checked "docker" @("push", $frontendImage) | Out-Null

$gsa = "$ServiceAccountName@$ProjectId.iam.gserviceaccount.com"
$saDescribe = & gcloud iam service-accounts describe $gsa "--project=$ProjectId" 2>&1
if ($LASTEXITCODE -ne 0) {
    Invoke-Checked "gcloud" @("iam", "service-accounts", "create", $ServiceAccountName, "--project=$ProjectId", "--display-name=AI DevOps Agent runtime") | Out-Null
}
Invoke-Checked "gcloud" @("projects", "add-iam-policy-binding", $ProjectId, "--member=serviceAccount:$gsa", "--role=roles/aiplatform.user") | Out-Null
Invoke-Checked "gcloud" @("iam", "service-accounts", "add-iam-policy-binding", $gsa, "--project=$ProjectId", "--role=roles/iam.workloadIdentityUser", "--member=serviceAccount:${ProjectId}.svc.id.goog[$Namespace/$ServiceAccountName]") | Out-Null
$clusterInfo = Invoke-Checked "gcloud" @("container", "clusters", "describe", $ClusterName, $locationFlag, "--project=$ProjectId", "--format=json") | ConvertFrom-Json
$isAutopilot = [bool]$clusterInfo.autopilot.enabled
$workloadPool = $clusterInfo.workloadIdentityConfig.workloadPool
if ([string]::IsNullOrWhiteSpace($workloadPool)) {
    if ($isAutopilot) {
        throw "The Autopilot cluster does not report a Workload Identity pool. Enable Workload Identity in GKE before rerunning."
    }
    Invoke-Checked "gcloud" @("container", "clusters", "update", $ClusterName, $locationFlag, "--project=$ProjectId", "--workload-pool=${ProjectId}.svc.id.goog") | Out-Null
    $nodePools = Invoke-Checked "gcloud" @("container", "node-pools", "list", "--cluster=$ClusterName", $locationFlag, "--project=$ProjectId", "--format=value(name)")
    foreach ($nodePool in $nodePools) {
        if (-not [string]::IsNullOrWhiteSpace($nodePool)) {
            Invoke-Checked "gcloud" @("container", "node-pools", "update", $nodePool, "--cluster=$ClusterName", $locationFlag, "--project=$ProjectId", "--workload-metadata=GKE_METADATA") | Out-Null
        }
    }
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ai-devops-agent-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $tempRoot | Out-Null
try {
    $replacements = @{
        "__PROJECT_ID__" = $ProjectId
        "__ARTIFACT_REGISTRY_REGION__" = $ArtifactRegion
        "__BACKEND_IMAGE__" = $backendImage
        "__FRONTEND_IMAGE__" = $frontendImage
        "__GCP_SERVICE_ACCOUNT_EMAIL__" = $gsa
    }
    $serviceAccountPath = $null
    foreach ($name in @("serviceaccount.yaml", "deployment.yaml", "frontend-deployment.yaml")) {
        $content = Get-Content -Raw (Join-Path $PSScriptRoot "..\kubernetes\$name")
        foreach ($key in $replacements.Keys) { $content = $content.Replace($key, $replacements[$key]) }
        $output = Join-Path $tempRoot $name
        Set-Content -Path $output -Value $content -Encoding utf8
        if ($name -eq "serviceaccount.yaml") { $serviceAccountPath = $output }
    }
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $PSScriptRoot "..\kubernetes\namespace.yaml")) | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", $serviceAccountPath) | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $PSScriptRoot "..\kubernetes\rbac.yaml")) | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $PSScriptRoot "..\kubernetes\service.yaml")) | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $tempRoot "deployment.yaml")) | Out-Null
    Invoke-Checked "kubectl" @("rollout", "status", "deployment/ai-devops-agent", "-n", $Namespace, "--timeout=5m") | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $tempRoot "frontend-deployment.yaml")) | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $PSScriptRoot "..\kubernetes\frontend-service.yaml")) | Out-Null
    Invoke-Checked "kubectl" @("rollout", "status", "deployment/ai-devops-frontend", "-n", $Namespace, "--timeout=5m") | Out-Null
    $external = ""
    for ($i = 0; $i -lt 30 -and [string]::IsNullOrWhiteSpace($external); $i++) {
        $external = (& kubectl get service ai-devops-frontend -n $Namespace -o "jsonpath={.status.loadBalancer.ingress[0].ip}{.status.loadBalancer.ingress[0].hostname}" 2>$null).ToString().Trim()
        if ([string]::IsNullOrWhiteSpace($external)) { Start-Sleep -Seconds 10 }
    }
    if ([string]::IsNullOrWhiteSpace($external)) { throw "Frontend LoadBalancer did not receive an external address." }
    Write-Host "Project: $ProjectId`nCluster: $ClusterName`nCluster location: $ClusterLocation`nArtifact Registry: $registry`nBackend image: $backendImage`nFrontend image: $frontendImage`nNamespace: $Namespace`nGoogle service account: $gsa`nFrontend external IP/hostname: $external`nDashboard URL: http://$external"
    Invoke-Checked "kubectl" @("get", "nodes") | Out-Null
    Invoke-Checked "kubectl" @("get", "pods", "-n", $Namespace) | Out-Null
    Invoke-Checked "kubectl" @("get", "svc", "-n", $Namespace) | Out-Null
}
finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
