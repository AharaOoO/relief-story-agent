[CmdletBinding()]
param(
  [switch]$DryRun,
  [int]$BackendPort = 8891,
  [int]$FrontendPort = 5173,
  [string]$HostAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
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
    backendPort = $BackendPort
    frontendPort = $FrontendPort
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
Write-Host ""

& powershell.exe `
  -NoProfile `
  -ExecutionPolicy Bypass `
  -File $WebLauncher `
  -NoBrowser `
  -BackendPort $BackendPort `
  -FrontendPort $FrontendPort `
  -HostAddress $HostAddress

if (-not (Test-Path -LiteralPath $ElectronNodeModules)) {
  Write-Host "Installing desktop client dependencies. This may take a few minutes..." -ForegroundColor Yellow
  npm --prefix $ElectronDir install
}

Write-Host "Opening desktop client window..." -ForegroundColor Yellow
npm --prefix $ElectronDir run dev
