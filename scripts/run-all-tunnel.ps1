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

# Resolve current LAN IPv4 so Expo QR is reachable from phone
$lanIp = $null
try {
  $lanIp = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
    Where-Object {
      $_.IPAddress -and
      $_.IPAddress -notlike "127.*" -and
      $_.IPAddress -notlike "169.254.*" -and
      $_.PrefixOrigin -ne "WellKnown"
    } |
    Select-Object -First 1 -ExpandProperty IPAddress
} catch {
  $lanIp = $null
}
if (-not $lanIp) {
  $lanIp = "127.0.0.1"
}

# Start backend in its own window
Start-Process powershell -WorkingDirectory $repoRoot -ArgumentList @(
  "-NoExit",
  "-NoProfile",
  "-Command",
  "python -m app.main"
)

# Start Expo in tunnel mode for QR fallback
Start-Process powershell -WorkingDirectory $mobileDir -ArgumentList @(
  "-NoExit",
  "-NoProfile",
  "-Command",
  "`$env:REACT_NATIVE_PACKAGER_HOSTNAME='$lanIp'; Remove-Item Env:CI -ErrorAction SilentlyContinue; `$npxPath = if (Test-Path 'D:\applications\npx.cmd') { 'D:\applications\npx.cmd' } else { 'npx' }; try { if (`$npxPath -eq 'npx') { & npx expo start --tunnel --port 8082 } else { & `$npxPath expo start --tunnel --port 8082 } } catch { Write-Host 'Tunnel startup failed, falling back to LAN mode...' -ForegroundColor Yellow; if (`$npxPath -eq 'npx') { & npx expo start --lan --port 8082 } else { & `$npxPath expo start --lan --port 8082 } }; if (`$LASTEXITCODE -ne 0) { Write-Host 'LAN startup failed, falling back to OFFLINE mode...' -ForegroundColor Yellow; if (`$npxPath -eq 'npx') { & npx expo start --offline --port 8082 } else { & `$npxPath expo start --offline --port 8082 } }"
)

Write-Host "Started e-OSEWS backend + Expo (TUNNEL mode)."
Write-Host "Web: http://127.0.0.1:8000/"
Write-Host "Expo startup mode: tunnel -> lan -> offline fallback on failure."
Write-Host "Expo host: $lanIp"
