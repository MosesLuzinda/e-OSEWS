$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$mobileDir = Join-Path $repoRoot "mobile-app"

function Stop-IfRunning {
  param([string]$imageName)
  try {
    taskkill /F /IM $imageName *> $null
  } catch {
    # Ignore if not running
  }
}

# Clean restart
Stop-IfRunning "python.exe"
Stop-IfRunning "node.exe"

# Ensure Expo runs in interactive mode
Remove-Item Env:CI -ErrorAction SilentlyContinue

# Start backend in its own window
Start-Process powershell -WorkingDirectory $repoRoot -ArgumentList @(
  "-NoExit",
  "-NoProfile",
  "-Command",
  "python -m app.main"
)

# Start Expo in its own window on 8082
Start-Process powershell -WorkingDirectory $mobileDir -ArgumentList @(
  "-NoExit",
  "-NoProfile",
  "-Command",
  "Remove-Item Env:CI -ErrorAction SilentlyContinue; if (Test-Path 'D:\applications\npx.cmd') { & 'D:\applications\npx.cmd' expo start --lan --port 8082 } else { npx expo start --lan --port 8082 }"
)

Write-Host "Started e-OSEWS backend + Expo."
Write-Host "Web: http://127.0.0.1:8000/"
Write-Host "Expo/QR: http://localhost:8082"
