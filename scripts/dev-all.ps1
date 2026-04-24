$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$mobileDir = Join-Path $repoRoot "mobile-app"

function Stop-NodeProcesses {
  try {
    taskkill /F /IM node.exe *> $null
  } catch {
    # ignore
  }
}

Stop-NodeProcesses

# Avoid Expo running in CI/non-interactive mode (hides QR + changes behavior)
Remove-Item Env:CI -ErrorAction SilentlyContinue

Start-Process powershell -WorkingDirectory $repoRoot -ArgumentList @(
  "-NoExit",
  "-NoProfile",
  "-Command",
  "python -m app.main"
)

Start-Process powershell -WorkingDirectory $mobileDir -ArgumentList @(
  "-NoExit",
  "-NoProfile",
  "-Command",
  "Remove-Item Env:CI -ErrorAction SilentlyContinue; npx expo start --lan -p 8081"
)
