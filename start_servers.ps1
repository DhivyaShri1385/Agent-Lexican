param(
    [switch]$SameWindow
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$venvCandidates = @(
    (Join-Path $projectRoot ".venv-1\Scripts\python.exe"),
    (Join-Path $projectRoot ".venv\Scripts\python.exe")
)

$pythonExe = $venvCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $pythonExe) {
    Write-Error "Could not find a virtual environment Python executable in .venv-1 or .venv."
    Write-Host "Create/activate your venv first, then run this script again."
    exit 1
}

$backendCommand = "Set-Location '$projectRoot'; & '$pythonExe' -m backend.app"
$frontendCommand = "Set-Location '$projectRoot'; & '$pythonExe' -m http.server 5500 -d frontend"

if ($SameWindow) {
    Write-Host "Starting backend in background job..."
    Start-Job -Name "ai-backend" -ScriptBlock {
        param($root, $py)
        Set-Location $root
        & $py -m backend.app
    } -ArgumentList $projectRoot, $pythonExe | Out-Null

    Write-Host "Starting frontend in background job..."
    Start-Job -Name "ai-frontend" -ScriptBlock {
        param($root, $py)
        Set-Location $root
        & $py -m http.server 5500 -d frontend
    } -ArgumentList $projectRoot, $pythonExe | Out-Null

    Write-Host "Servers started as jobs: ai-backend, ai-frontend"
    Write-Host "Use: Get-Job"
    Write-Host "Logs: Receive-Job -Name ai-backend -Keep"
    Write-Host "Stop: Stop-Job -Name ai-backend,ai-frontend"
    exit 0
}

Write-Host "Starting backend server in a new PowerShell window..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $backendCommand
) | Out-Null

Write-Host "Starting frontend server in a new PowerShell window..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $frontendCommand
) | Out-Null

Write-Host "Done."
Write-Host "Frontend: http://127.0.0.1:5500"
Write-Host "Backend health: http://127.0.0.1:5000/health"
