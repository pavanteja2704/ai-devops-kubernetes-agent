$ErrorActionPreference = "Stop"

$script = Get-Content -LiteralPath (Join-Path $PSScriptRoot "deploy.ps1") -Raw
$functionNames = @("ConvertTo-ProcessArgument", "Resolve-NativeCommand", "Invoke-Native")
$definitions = foreach ($name in $functionNames) {
    $match = [regex]::Match($script, '(?s)function ' + $name + ' \{.*?\r?\n\}')
    if (-not $match.Success) {
        throw "Function $name was not found in deploy.ps1."
    }
    $match.Value
}
Invoke-Expression ($definitions -join "`n")

$docker = Invoke-Native "docker" @("info") 120 "Docker info wrapper test"
if ($docker.GetType().Name -ne "PSCustomObject" -or $docker.ExitCode -ne 0 -or $docker.TimedOut) {
    throw "docker info wrapper test failed: ExitCode=$($docker.ExitCode), TimedOut=$($docker.TimedOut)"
}

$failure = Invoke-Native "cmd.exe" @("/c", "exit", "7") 30 "Failure wrapper test"
if ($failure.GetType().Name -ne "PSCustomObject" -or $failure.ExitCode -ne 7 -or $failure.TimedOut) {
    throw "Failure wrapper test failed: ExitCode=$($failure.ExitCode), TimedOut=$($failure.TimedOut)"
}

$timeout = Invoke-Native "powershell.exe" @("-NoProfile", "-NonInteractive", "-Command", "Start-Sleep -Seconds 3") 1 "Timeout wrapper test"
if ($timeout.GetType().Name -ne "PSCustomObject" -or -not $timeout.TimedOut -or $timeout.ExitCode -ne -1) {
    throw "Timeout wrapper test failed: ExitCode=$($timeout.ExitCode), TimedOut=$($timeout.TimedOut)"
}

Write-Output "Native wrapper tests: docker success, non-zero failure, and timeout passed"
