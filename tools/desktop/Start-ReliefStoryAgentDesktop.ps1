[CmdletBinding()]
param(
  [switch]$DryRun,
  [int]$BackendPort = 8891,
  [int]$FrontendPort = 5173,
  [string]$HostAddress = "127.0.0.1",
  [string]$ComfyUiEndpoint = "http://127.0.0.1:8188",
  [string]$DesktopUserDataDir = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($DesktopUserDataDir)) {
  $DesktopUserDataDir = Join-Path $RepoRoot "relief_story_state\desktop"
}
$DesktopSettingsPath = Join-Path $DesktopUserDataDir "settings.json"
$DesktopSettings = $null
if (Test-Path -LiteralPath $DesktopSettingsPath) {
  $DesktopSettings = Get-Content -LiteralPath $DesktopSettingsPath -Raw | ConvertFrom-Json
}

function Get-DesktopSetting {
  param(
    [string]$Name,
    $Fallback
  )

  if (
    $null -ne $DesktopSettings -and
    ($DesktopSettings.PSObject.Properties.Name -contains $Name) -and
    -not [string]::IsNullOrWhiteSpace([string]$DesktopSettings.$Name)
  ) {
    return $DesktopSettings.$Name
  }

  return $Fallback
}

$HostAddress = [string](Get-DesktopSetting -Name "host" -Fallback $HostAddress)
$BackendPort = [int](Get-DesktopSetting -Name "backendPort" -Fallback $BackendPort)
$FrontendPort = [int](Get-DesktopSetting -Name "frontendPort" -Fallback $FrontendPort)
$ComfyUiEndpoint = [string](Get-DesktopSetting -Name "comfyUiEndpoint" -Fallback $ComfyUiEndpoint)
$WorkflowPath = [string](Get-DesktopSetting -Name "workflowPath" -Fallback "D:/ComfyUI/workflows/ltx23_four_grid.json")
$StateDir = [string](Get-DesktopSetting -Name "stateDir" -Fallback (Join-Path $DesktopUserDataDir "state"))
$LogDir = [string](Get-DesktopSetting -Name "logDir" -Fallback (Join-Path $DesktopUserDataDir "logs"))
$WebLauncher = Join-Path $RepoRoot "tools\desktop\Start-ReliefStoryAgent.ps1"
$ElectronDir = Join-Path $RepoRoot "desktop\electron"
$ElectronPackage = Join-Path $ElectronDir "package.json"
$ElectronNodeModules = Join-Path $ElectronDir "node_modules"
$FrontendUrl = "http://${HostAddress}:${FrontendPort}/"

if ($DryRun) {
  [ordered]@{
    shell = "electron"
    repoRoot = $RepoRoot
    webLauncher = $WebLauncher
    electronDir = $ElectronDir
    electronPackage = $ElectronPackage
    desktopUserDataDir = $DesktopUserDataDir
    desktopSettingsPath = $DesktopSettingsPath
    backendPort = $BackendPort
    frontendPort = $FrontendPort
    hostAddress = $HostAddress
    comfyUiEndpoint = $ComfyUiEndpoint
    workflowPath = $WorkflowPath
    stateDir = $StateDir
    logDir = $LogDir
    frontendUrl = $FrontendUrl
    command = "npm --prefix `"$ElectronDir`" run dev"
  } | ConvertTo-Json -Depth 4
  exit 0
}

if (-not (Test-Path -LiteralPath $WebLauncher)) {
  throw "Web launcher not found: $WebLauncher"
}

if (-not (Test-Path -LiteralPath $ElectronPackage)) {
  throw "Electron package not found: $ElectronPackage"
}

Write-Host ""
Write-Host " RELIEF STORY AGENT DESKTOP " -ForegroundColor Black -BackgroundColor Yellow
Write-Host " Shell    Electron desktop client" -ForegroundColor Cyan
Write-Host " UI       $FrontendUrl" -ForegroundColor Cyan
Write-Host " Config   $DesktopSettingsPath" -ForegroundColor DarkYellow
Write-Host ""

New-Item -ItemType Directory -Force -Path $DesktopUserDataDir | Out-Null

& powershell.exe `
  -NoProfile `
  -ExecutionPolicy Bypass `
  -File $WebLauncher `
  -NoBrowser `
  -BackendPort $BackendPort `
  -FrontendPort $FrontendPort `
  -HostAddress $HostAddress `
  -ComfyUiEndpoint $ComfyUiEndpoint `
  -StateDir $StateDir `
  -LogDir $LogDir

if (-not (Test-Path -LiteralPath $ElectronNodeModules)) {
  Write-Host "Installing desktop client dependencies. This may take a few minutes..." -ForegroundColor Yellow
  npm --prefix $ElectronDir install
}

Write-Host "Opening desktop client window..." -ForegroundColor Yellow
$env:RELIEF_DESKTOP_USER_DATA_DIR = $DesktopUserDataDir
$env:RELIEF_DESKTOP_HOST = $HostAddress
$env:RELIEF_BACKEND_PORT = [string]$BackendPort
$env:RELIEF_FRONTEND_PORT = [string]$FrontendPort
$env:RELIEF_COMFYUI_ENDPOINT = $ComfyUiEndpoint
$env:RELIEF_WORKFLOW_PATH = $WorkflowPath
npm --prefix $ElectronDir run dev
