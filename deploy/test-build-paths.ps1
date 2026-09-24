$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendDockerfile = Join-Path $repositoryRoot "Dockerfile"
$frontendDockerfile = Join-Path $repositoryRoot "frontend\Dockerfile"
$frontendContext = Join-Path $repositoryRoot "frontend"

foreach ($path in @($backendDockerfile, $frontendDockerfile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Expected Dockerfile was not found: $path"
    }
}
foreach ($path in @($repositoryRoot, $frontendContext)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Expected Docker build context was not found: $path"
    }
}

Write-Output "Docker build paths: backend root context and frontend context validated"
