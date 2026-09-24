[CmdletBinding()]
param(
    [string]$InputPath,
    [switch]$LocalValidation
)

$ErrorActionPreference = "Stop"
Write-Host "[Stage 0] Starting deploy.ps1"
if ([string]::IsNullOrWhiteSpace($InputPath)) {
    $InputPath = Join-Path $PSScriptRoot "inputs.yaml"
}
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Namespace = "ai-devops-agent"
$Repository = "ai-devops-agent-repo"
$BackendName = "ai-devops-agent"
$FrontendName = "ai-devops-frontend"
$ServiceAccountName = "ai-devops-agent-sa"
$MinimumCpuMilli = 3500
$MinimumMemoryMi = 8192

function ConvertTo-ProcessArgument {
    param([string]$Value)
    if ($Value -notmatch '[\s"]' -and $Value.Length -gt 0) {
        return $Value
    }
    return '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

function Resolve-NativeCommand {
    param([string]$Command)

    $commands = @(Get-Command $Command -All -ErrorAction Stop)
    $applications = @($commands | Where-Object { $_.CommandType -eq "Application" })
    if ($applications.Count -gt 0) {
        $preferred = $applications | Sort-Object {
            $extension = [System.IO.Path]::GetExtension($_.Source).ToLowerInvariant()
            switch ($extension) {
                ".cmd" { 0 }
                ".exe" { 1 }
                default { 2 }
            }
        } | Select-Object -First 1
        return [pscustomobject]@{
            FilePath = if ($preferred.Source) { $preferred.Source } else { $preferred.Path }
            PrefixArguments = @()
        }
    }

    $script = $commands | Where-Object {
        $_.CommandType -eq "ExternalScript" -and $_.Source -and $_.Source.EndsWith(".ps1", [System.StringComparison]::OrdinalIgnoreCase)
    } | Select-Object -First 1
    if ($script) {
        $powershell = Get-Command powershell.exe -ErrorAction Stop
        return [pscustomobject]@{
            FilePath = $powershell.Source
            PrefixArguments = @("-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $script.Source)
        }
    }

    throw "No executable or PowerShell wrapper was found for '$Command'."
}

function Invoke-Native {
    param(
        [string]$Command,
        [string[]]$Arguments,
        [int]$TimeoutSeconds = 600,
        [string]$Stage = $Command
    )

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    $displayCommand = "$Command $($Arguments -join ' ')"
    try {
        # Start-Process keeps native stderr out of PowerShell's error stream.
        # Some successful gcloud commands intentionally write status messages
        # to stderr, so only the process exit code determines success.
        $resolved = Resolve-NativeCommand $Command
        $allArguments = @($resolved.PrefixArguments) + @($Arguments)
        $argumentLine = ($allArguments | ForEach-Object { ConvertTo-ProcessArgument ([string]$_) }) -join " "
        Write-Host "[stage] Starting $Stage`: $displayCommand (timeout ${TimeoutSeconds}s)"
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $resolved.FilePath
        $startInfo.Arguments = $argumentLine
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $startInfo
        $null = $process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $completed = [bool]$process.WaitForExit($TimeoutSeconds * 1000)
        $timedOut = -not $completed
        if ($timedOut) {
            Write-Host "[stage] Timeout reached for $Stage; stopping process $($process.Id)."
            $process.Kill()
            $null = $process.WaitForExit(1000)
        }
        if ($timedOut) {
            $exitCode = [int]-1
        } else {
            $stdoutTask.GetAwaiter().GetResult() | Set-Content -LiteralPath $stdoutPath -Encoding utf8
            $stderrTask.GetAwaiter().GetResult() | Set-Content -LiteralPath $stderrPath -Encoding utf8
            $exitCode = [int]$process.ExitCode
        }
        if ($timedOut) {
            $stdoutTask.GetAwaiter().GetResult() | Set-Content -LiteralPath $stdoutPath -Encoding utf8
            $stderrTask.GetAwaiter().GetResult() | Set-Content -LiteralPath $stderrPath -Encoding utf8
        }
        $stdout = if (Test-Path -LiteralPath $stdoutPath) { @(Get-Content -LiteralPath $stdoutPath) } else { @() }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { @(Get-Content -LiteralPath $stderrPath) } else { @() }
        $result = [pscustomobject]@{
            ExitCode = $exitCode
            Output = $stdout
            ErrorOutput = $stderr
            TimedOut = $timedOut
            Stage = $Stage
            CommandLine = $displayCommand
        }
        return ,$result
    }
    finally {
        if (Test-Path -LiteralPath $stdoutPath) {
            Remove-Item -LiteralPath $stdoutPath -Force
        }
        if (Test-Path -LiteralPath $stderrPath) {
            Remove-Item -LiteralPath $stderrPath -Force
        }
    }
}

function Invoke-Checked {
    param(
        [string]$Command,
        [string[]]$Arguments,
        [int]$TimeoutSeconds = 600,
        [string]$Stage = $Command
    )
    $result = Invoke-Native $Command $Arguments $TimeoutSeconds $Stage
    if ($result.TimedOut) {
        $details = @($result.Output) + @($result.ErrorOutput)
        throw "$Stage timed out after $TimeoutSeconds seconds. Command: $($result.CommandLine)`n$($details -join [Environment]::NewLine)"
    }
    if ($result.ExitCode -ne 0) {
        $details = @($result.Output) + @($result.ErrorOutput)
        throw "$Stage failed with exit code $($result.ExitCode). Command: $($result.CommandLine)`n$($details -join [Environment]::NewLine)"
    }
    Write-Host "[stage] Completed $Stage."
    return @($result.Output)
}

function Write-Stage {
    param([string]$Message)
    Write-Host "`n=== $Message ==="
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

function Get-GkeLocationType {
    param([string]$Location)

    if ($Location -match '^[a-z]+(?:-[a-z0-9]+)*[0-9]-[a-z]$') {
        return "zone"
    }
    if ($Location -match '^[a-z]+(?:-[a-z0-9]+)*[0-9]$') {
        return "region"
    }
    throw "Invalid GKE location '$Location'. Use a zonal location such as us-central1-a or a regional location such as us-central1."
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

function Test-AllocatableCapacity {
    param(
        [int]$TotalCpuMilli,
        [int]$TotalMemoryMi,
        [int]$MinimumCpuMilli = 3500,
        [int]$MinimumMemoryMi = 8192
    )

    return $TotalCpuMilli -ge $MinimumCpuMilli -and $TotalMemoryMi -ge $MinimumMemoryMi
}

function Test-WorkloadIdentityPool {
    param(
        [string]$WorkloadPool,
        [string]$ProjectId
    )

    return $WorkloadPool -eq "$ProjectId.svc.id.goog"
}

function Get-NodePoolMetadataMode {
    param([object]$NodePool)

    if ($null -eq $NodePool.config -or $null -eq $NodePool.config.workloadMetadataConfig) {
        return ""
    }
    return [string]$NodePool.config.workloadMetadataConfig.mode
}

Write-Host "[Stage 1] Loading inputs.yaml"
if (-not (Test-Path -LiteralPath $InputPath)) { throw "Input file not found: $InputPath" }
$inputLines = Get-Content -LiteralPath $InputPath
Write-Host "[Stage 1] Loaded inputs.yaml"

Write-Host "[Stage 2] Validating inputs"
$ProjectId = Get-YamlScalar $inputLines "^project_id:"
Write-Host "[Stage 2] Validated project_id"
$ClusterName = Get-YamlScalar $inputLines "^\s+name:"
Write-Host "[Stage 2] Validated cluster.name"
$ClusterLocation = Get-YamlScalar $inputLines "^\s+location:"
Write-Host "[Stage 2] Validated cluster.location: $ClusterLocation"
if ($LocalValidation) {
    $localLocationType = Get-GkeLocationType $ClusterLocation
    Write-Host "[Stage 2] Validated GKE location type: $localLocationType"
    Write-Host "[Stage 3] Required-tool check skipped in local validation mode"
    Write-Host "[Local validation] Initialization completed without external access."
    exit 0
}

Write-Host "[Stage 3] Checking required tools"
foreach ($tool in @("gcloud", "kubectl", "docker")) {
    Write-Host "[Stage 3] Checking $tool"
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is required and was not found on PATH." }
}
Write-Host "[Stage 3] Required tools found"
Write-Host "[Stage 4] Checking authentication and Docker"
Invoke-Checked "docker" @("info") 120 "Docker daemon check" | Out-Null
Invoke-Checked "gcloud" @("auth", "list", "--filter=status:ACTIVE", "--format=value(account)") 120 "gcloud authentication check" | Out-Null
Invoke-Checked "gcloud" @("config", "set", "project", $ProjectId) 120 "Set gcloud project" | Out-Null
Write-Host "[Stage 4] Authentication and Docker checks completed"

$LocationType = Get-GkeLocationType $ClusterLocation
$ArtifactRegion = if ($LocationType -eq "zone" -and $ClusterLocation -match "^(.*)-[a-z]$") { $Matches[1] } else { $ClusterLocation }

Write-Host "[Stage 5] Validating GKE cluster location and connectivity"
$locationFlag = if ($LocationType -eq "region") { "--region=$ClusterLocation" } else { "--zone=$ClusterLocation" }
try {
    Invoke-Checked "gcloud" @("container", "clusters", "describe", $ClusterName, $locationFlag, "--project=$ProjectId", "--format=value(name)") 300 "Validate GKE cluster location" | Out-Null
} catch {
    throw "GKE cluster '$ClusterName' was not found at location '$ClusterLocation' in project '$ProjectId'. $($_.Exception.Message)"
}
Invoke-Checked "gcloud" @("container", "clusters", "get-credentials", $ClusterName, $locationFlag, "--project=$ProjectId") 300 "Get GKE credentials" | Out-Null
Invoke-Checked "kubectl" @("cluster-info") 120 "Check Kubernetes connectivity" | Out-Null
$nodeRows = Invoke-Checked "kubectl" @("get", "nodes", "-o", "jsonpath={range .items[*]}{.metadata.name}{','}{.status.allocatable.cpu}{','}{.status.allocatable.memory}{'\n'}{end}") 120 "Read node allocatable capacity"
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
if (-not (Test-AllocatableCapacity $totalCpu $totalMemory $MinimumCpuMilli $MinimumMemoryMi)) {
    throw "Cluster allocatable capacity is below the deployment minimum of $MinimumCpuMilli mCPU allocatable CPU and $MinimumMemoryMi MiB allocatable memory. The recommended node size is at least 4 vCPU / 8 GiB; normal Kubernetes/GKE system reservations can reduce allocatable CPU below the physical CPU size. Detected approximately $totalCpu mCPU and $totalMemory MiB. Resize the cluster manually; deploy.ps1 will not resize or recreate node pools."
}

Write-Host "[Stage 6] Enabling required Google Cloud APIs"
Invoke-Checked "gcloud" @("services", "enable", "container.googleapis.com", "artifactregistry.googleapis.com", "aiplatform.googleapis.com", "--project=$ProjectId") 600 "Enable required Google Cloud APIs" | Out-Null

Write-Host "[Stage 7] Preparing Artifact Registry"
$repoCheck = Invoke-Native "gcloud" @("artifacts", "repositories", "describe", $Repository, "--location=$ArtifactRegion", "--project=$ProjectId") 300 "Check Artifact Registry repository"
if ($repoCheck.TimedOut) {
    $details = @($repoCheck.Output) + @($repoCheck.ErrorOutput)
    throw "Artifact Registry repository check timed out after 300 seconds. Command: $($repoCheck.CommandLine)`n$($details -join [Environment]::NewLine)"
}
if ($repoCheck.ExitCode -ne 0) {
    Invoke-Checked "gcloud" @("artifacts", "repositories", "create", $Repository, "--repository-format=docker", "--location=$ArtifactRegion", "--project=$ProjectId") 600 "Create Artifact Registry repository" | Out-Null
}
Invoke-Checked "gcloud" @("auth", "configure-docker", "$ArtifactRegion-docker.pkg.dev", "--quiet") 300 "Configure Docker authentication" | Out-Null

$registry = "$ArtifactRegion-docker.pkg.dev/$ProjectId/$Repository"
$backendImage = "$registry/$BackendName`:latest"
$frontendImage = "$registry/$FrontendName`:latest"
Write-Host "[Stage 8] Building and pushing container images"
$backendDockerfile = Join-Path $RepositoryRoot "Dockerfile"
$backendBuildContext = $RepositoryRoot
$frontendDockerfile = Join-Path $RepositoryRoot "frontend\Dockerfile"
$frontendBuildContext = Join-Path $RepositoryRoot "frontend"
if (-not (Test-Path -LiteralPath $backendDockerfile -PathType Leaf)) {
    throw "Backend Dockerfile was not found: $backendDockerfile"
}
if (-not (Test-Path -LiteralPath $backendBuildContext -PathType Container)) {
    throw "Backend Docker build context was not found: $backendBuildContext"
}
if (-not (Test-Path -LiteralPath $frontendDockerfile -PathType Leaf)) {
    throw "Frontend Dockerfile was not found: $frontendDockerfile"
}
if (-not (Test-Path -LiteralPath $frontendBuildContext -PathType Container)) {
    throw "Frontend Docker build context was not found: $frontendBuildContext"
}
Write-Host "[Stage 8] Backend Dockerfile: $backendDockerfile"
Write-Host "[Stage 8] Backend build context: $backendBuildContext"
Invoke-Checked "docker" @("build", "-f", $backendDockerfile, "-t", $backendImage, $backendBuildContext) 1800 "Build backend image" | Out-Null
Write-Host "[Stage 8] Frontend Dockerfile: $frontendDockerfile"
Write-Host "[Stage 8] Frontend build context: $frontendBuildContext"
Invoke-Checked "docker" @("build", "-f", $frontendDockerfile, "-t", $frontendImage, $frontendBuildContext) 1800 "Build frontend image" | Out-Null
Invoke-Checked "docker" @("push", $backendImage) 1200 "Push backend image" | Out-Null
Invoke-Checked "docker" @("push", $frontendImage) 1200 "Push frontend image" | Out-Null

Write-Host "[Stage 9] Configuring runtime service account and Workload Identity"
$gsa = "$ServiceAccountName@$ProjectId.iam.gserviceaccount.com"
$saDescribe = Invoke-Native "gcloud" @("iam", "service-accounts", "describe", $gsa, "--project=$ProjectId") 300 "Check runtime service account"
if ($saDescribe.TimedOut) {
    $details = @($saDescribe.Output) + @($saDescribe.ErrorOutput)
    throw "Runtime service account check timed out after 300 seconds. Command: $($saDescribe.CommandLine)`n$($details -join [Environment]::NewLine)"
}
if ($saDescribe.ExitCode -ne 0) {
    Invoke-Checked "gcloud" @("iam", "service-accounts", "create", $ServiceAccountName, "--project=$ProjectId", "--display-name=AI DevOps Agent runtime") 600 "Create runtime service account" | Out-Null
}
Invoke-Checked "gcloud" @("projects", "add-iam-policy-binding", $ProjectId, "--member=serviceAccount:$gsa", "--role=roles/aiplatform.user") 600 "Grant Vertex AI runtime role" | Out-Null
$clusterJson = Invoke-Checked "gcloud" @("container", "clusters", "describe", $ClusterName, $locationFlag, "--project=$ProjectId", "--format=json") 300 "Read Workload Identity configuration"
$clusterInfo = ($clusterJson -join [Environment]::NewLine) | ConvertFrom-Json
$isAutopilot = [bool]$clusterInfo.autopilot.enabled
$workloadPool = $clusterInfo.workloadIdentityConfig.workloadPool
if (Test-WorkloadIdentityPool $workloadPool $ProjectId) {
    Write-Host "[Stage 9] Workload Identity already enabled"
} else {
    if ($isAutopilot) {
        throw "The Autopilot cluster does not report the expected Workload Identity pool '$ProjectId.svc.id.goog'."
    }
    Write-Host "[Stage 9] Workload Identity not enabled; enabling it"
    Invoke-Checked "gcloud" @("container", "clusters", "update", $ClusterName, $locationFlag, "--project=$ProjectId", "--workload-pool=${ProjectId}.svc.id.goog") 1200 "Enable GKE Workload Identity Federation" | Out-Null
    $verifiedPool = Invoke-Checked "gcloud" @("container", "clusters", "describe", $ClusterName, $locationFlag, "--project=$ProjectId", "--format=value(workloadIdentityConfig.workloadPool)") 300 "Verify GKE Workload Identity Federation"
    $verifiedPoolValue = ($verifiedPool -join "").Trim()
    if (-not (Test-WorkloadIdentityPool $verifiedPoolValue $ProjectId)) {
        throw "GKE Workload Identity verification failed. Expected '$ProjectId.svc.id.goog', got '$verifiedPoolValue'."
    }
    Write-Host "[Stage 9] Workload Identity enabled"
}

if (-not $isAutopilot) {
    Write-Host "[Stage 9] Checking node pool metadata configuration"
    $nodePoolJson = Invoke-Checked "gcloud" @("container", "node-pools", "list", "--cluster=$ClusterName", $locationFlag, "--project=$ProjectId", "--format=json") 300 "Read GKE node pool metadata configuration"
    $nodePools = (($nodePoolJson -join [Environment]::NewLine) | ConvertFrom-Json)
    foreach ($nodePool in @($nodePools)) {
        if ($null -eq $nodePool -or [string]::IsNullOrWhiteSpace([string]$nodePool.name)) { continue }
        $metadataMode = Get-NodePoolMetadataMode $nodePool
        if ($metadataMode -eq "GKE_METADATA") {
            Write-Host "[Stage 9] Node pool $($nodePool.name) already uses GKE_METADATA"
            continue
        }
        Write-Host "[Stage 9] Enabling GKE metadata server on node pool $($nodePool.name)"
        Invoke-Checked "gcloud" @("container", "node-pools", "update", $nodePool.name, "--cluster=$ClusterName", $locationFlag, "--project=$ProjectId", "--workload-metadata=GKE_METADATA") 1200 "Enable GKE metadata server on node pool $($nodePool.name)" | Out-Null
    }
    Write-Host "[Stage 9] GKE metadata server enabled"
}
Invoke-Checked "gcloud" @("iam", "service-accounts", "add-iam-policy-binding", $gsa, "--project=$ProjectId", "--role=roles/iam.workloadIdentityUser", "--member=serviceAccount:${ProjectId}.svc.id.goog[$Namespace/$ServiceAccountName]") 600 "Grant Workload Identity binding" | Out-Null

Write-Host "[Stage 10] Rendering Kubernetes manifests"
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
    Write-Host "[Stage 11] Applying Kubernetes resources"
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $PSScriptRoot "..\kubernetes\namespace.yaml")) 300 "Apply namespace" | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", $serviceAccountPath) 300 "Apply Kubernetes service account" | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $PSScriptRoot "..\kubernetes\rbac.yaml")) 300 "Apply read-only RBAC" | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $PSScriptRoot "..\kubernetes\service.yaml")) 300 "Apply backend service" | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $tempRoot "deployment.yaml")) 300 "Apply backend deployment" | Out-Null
    Invoke-Checked "kubectl" @("rollout", "status", "deployment/ai-devops-agent", "-n", $Namespace, "--timeout=5m") 360 "Wait for backend rollout" | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $tempRoot "frontend-deployment.yaml")) 300 "Apply frontend deployment" | Out-Null
    Invoke-Checked "kubectl" @("apply", "-f", (Join-Path $PSScriptRoot "..\kubernetes\frontend-service.yaml")) 300 "Apply frontend service" | Out-Null
    Invoke-Checked "kubectl" @("rollout", "status", "deployment/ai-devops-frontend", "-n", $Namespace, "--timeout=5m") 360 "Wait for frontend rollout" | Out-Null
    Write-Host "[Stage 12] Waiting for frontend LoadBalancer address"
    $external = ""
    for ($i = 0; $i -lt 30 -and [string]::IsNullOrWhiteSpace($external); $i++) {
        Write-Host "[stage] LoadBalancer address poll $($i + 1)/30."
        $externalResult = Invoke-Native "kubectl" @("get", "service", "ai-devops-frontend", "-n", $Namespace, "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}{.status.loadBalancer.ingress[0].hostname}") 30 "Read frontend LoadBalancer address"
        if ($externalResult.ExitCode -ne 0) {
            $details = @($externalResult.Output) + @($externalResult.ErrorOutput)
            throw "kubectl failed while checking the frontend LoadBalancer with exit code $($externalResult.ExitCode). Command: $($externalResult.CommandLine)`n$($details -join [Environment]::NewLine)"
        }
        $external = (@($externalResult.Output) -join "").Trim()
        if ([string]::IsNullOrWhiteSpace($external)) { Start-Sleep -Seconds 10 }
    }
    if ([string]::IsNullOrWhiteSpace($external)) { throw "Frontend LoadBalancer did not receive an external address." }
    Write-Host "Project: $ProjectId`nCluster: $ClusterName`nCluster location: $ClusterLocation`nArtifact Registry: $registry`nBackend image: $backendImage`nFrontend image: $frontendImage`nNamespace: $Namespace`nGoogle service account: $gsa`nFrontend external IP/hostname: $external`nDashboard URL: http://$external"
    Write-Host "[Stage 13] Verifying deployed resources"
    Invoke-Checked "kubectl" @("get", "nodes") 120 "Verify nodes" | Out-Null
    Invoke-Checked "kubectl" @("get", "pods", "-n", $Namespace) 120 "Verify deployed pods" | Out-Null
    Invoke-Checked "kubectl" @("get", "svc", "-n", $Namespace) 120 "Verify deployed services" | Out-Null
}
finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
