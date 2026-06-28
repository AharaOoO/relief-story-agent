[CmdletBinding()]
param(
  [switch]$DryRun,
  [switch]$NoBrowser,
  [int]$BackendPort = 8891,
  [int]$FrontendPort = 5173,
  [string]$HostAddress = "127.0.0.1",
  [string]$ComfyUiEndpoint = "http://127.0.0.1:8188"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$FrontendDir = Join-Path $RepoRoot "frontend"
$StateDir = Join-Path $RepoRoot "relief_story_state"
$LogDir = Join-Path $StateDir "launcher-logs"
$ModelConfig = Join-Path $RepoRoot "relief_story_agent\examples\model_config.local.example.json"
$BackendUrl = "http://${HostAddress}:${BackendPort}"
$FrontendUrl = "http://${HostAddress}:${FrontendPort}/"
$BackendLog = Join-Path $LogDir "backend.log"
$FrontendLog = Join-Path $LogDir "frontend.log"

function Test-PortListening {
  param([int]$Port)

  $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return $null -ne $connection
}

function Wait-HttpReady {
  param(
    [string]$Url,
    [int]$TimeoutSeconds = 45
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Seconds 1
    }
  } while ((Get-Date) -lt $deadline)

  return $false
}

function Start-HiddenPowerShell {
  param(
    [string]$Command,
    [string]$WorkingDirectory
  )

  Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command) `
    -WorkingDirectory $WorkingDirectory `
    -WindowStyle Hidden | Out-Null
}

$backendCommand = @"
`$env:PYTHONPATH = '$RepoRoot;' + `$env:PYTHONPATH
python -m relief_story_agent.server --host $HostAddress --port $BackendPort --state-dir '$StateDir' --model-config '$ModelConfig' --comfyui-endpoint '$ComfyUiEndpoint' --max-workers 2 --lease-seconds 300 --recovery-poll-seconds 5 *> '$BackendLog'
"@

$frontendCommand = @"
Set-Location -LiteralPath '$FrontendDir'
npm run dev -- --host $HostAddress --port $FrontendPort *> '$FrontendLog'
"@

if ($DryRun) {
  [ordered]@{
    repoRoot = $RepoRoot
    frontendDir = $FrontendDir
    stateDir = $StateDir
    logDir = $LogDir
    backendPort = $BackendPort
    frontendPort = $FrontendPort
    backendUrl = $BackendUrl
    frontendUrl = $FrontendUrl
    backendLog = $BackendLog
    frontendLog = $FrontendLog
    backendCommand = "python -m relief_story_agent.server --host $HostAddress --port $BackendPort"
    frontendCommand = "npm run dev -- --host $HostAddress --port $FrontendPort"
  } | ConvertTo-Json -Depth 4
  exit 0
}

if (-not (Test-Path -LiteralPath $FrontendDir)) {
  throw "Frontend directory not found: $FrontendDir"
}

if (-not (Test-Path -LiteralPath $ModelConfig)) {
  throw "Model config not found: $ModelConfig"
}

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Write-Host ""
Write-Host " RELIEF STORY AGENT " -ForegroundColor Black -BackgroundColor Yellow
Write-Host " API      $BackendUrl" -ForegroundColor Cyan
Write-Host " UI       $FrontendUrl" -ForegroundColor Cyan
Write-Host " Logs     $LogDir" -ForegroundColor DarkYellow
Write-Host ""

if (Test-PortListening -Port $BackendPort) {
  Write-Host "Backend is already listening on port $BackendPort." -ForegroundColor Green
} else {
  Write-Host "Starting backend service..." -ForegroundColor Yellow
  Start-HiddenPowerShell -Command $backendCommand -WorkingDirectory $RepoRoot
}

if (Test-PortListening -Port $FrontendPort) {
  Write-Host "Frontend is already listening on port $FrontendPort." -ForegroundColor Green
} else {
  if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "Installing frontend dependencies. This may take a few minutes..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    npm install
    Pop-Location
  }

  Write-Host "Starting frontend service..." -ForegroundColor Yellow
  Start-HiddenPowerShell -Command $frontendCommand -WorkingDirectory $FrontendDir
}

$backendReady = Wait-HttpReady -Url "$BackendUrl/api/health" -TimeoutSeconds 45
$frontendReady = Wait-HttpReady -Url $FrontendUrl -TimeoutSeconds 45

if (-not $backendReady) {
  Write-Warning "Backend did not respond in time. Check $BackendLog"
}
if (-not $frontendReady) {
  Write-Warning "Frontend did not respond in time. Check $FrontendLog"
}

if (-not $NoBrowser) {
  Start-Process $FrontendUrl | Out-Null
}

Write-Host ""
Write-Host "Launcher finished. You can close this window after the UI opens." -ForegroundColor Green
