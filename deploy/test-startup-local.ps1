$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "deploy.ps1"
$output = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $scriptPath -LocalValidation 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Local startup validation failed with exit code $LASTEXITCODE`n$($output -join [Environment]::NewLine)"
}

$text = $output -join [Environment]::NewLine
foreach ($expected in @(
    "[Stage 0] Starting deploy.ps1",
    "[Stage 1] Loading inputs.yaml",
    "[Stage 2] Validating inputs",
    "[Stage 3]"
)) {
    if ($text -notmatch [regex]::Escape($expected)) {
        throw "Local startup validation did not reach '$expected'.`n$text"
    }
}

Write-Output "Local startup validation: stages 0-3 reached without cloud or cluster access"
