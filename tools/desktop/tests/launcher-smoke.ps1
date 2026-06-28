$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$launcher = Join-Path $Root "tools\desktop\Start-ReliefStoryAgent.ps1"
$desktopLauncher = Join-Path $Root "tools\desktop\Start-ReliefStoryAgentDesktop.ps1"
$installer = Join-Path $Root "tools\desktop\Install-Shortcut.ps1"
$desktopInstaller = Join-Path $Root "tools\desktop\Install-DesktopShortcut.ps1"
$electronPackage = Join-Path $Root "desktop\electron\package.json"

foreach ($path in @($launcher, $desktopLauncher, $installer, $desktopInstaller, $electronPackage)) {
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Missing expected desktop file: $path"
  }
}

$launcherPlan = & $launcher -DryRun | ConvertFrom-Json
if ($launcherPlan.backendPort -ne 8891) {
  throw "Expected backend port 8891, got $($launcherPlan.backendPort)"
}
if ($launcherPlan.frontendPort -ne 5173) {
  throw "Expected frontend port 5173, got $($launcherPlan.frontendPort)"
}
if ($launcherPlan.frontendUrl -ne "http://127.0.0.1:5173/") {
  throw "Unexpected frontend URL: $($launcherPlan.frontendUrl)"
}

$shortcutPlan = & $installer -DryRun | ConvertFrom-Json
if (-not $shortcutPlan.shortcutPath.EndsWith("Relief Story Agent.lnk")) {
  throw "Unexpected shortcut path: $($shortcutPlan.shortcutPath)"
}
if (-not $shortcutPlan.iconPath.EndsWith("relief-story-agent.ico")) {
  throw "Unexpected icon path: $($shortcutPlan.iconPath)"
}

$desktopPlan = & $desktopLauncher -DryRun | ConvertFrom-Json
if ($desktopPlan.shell -ne "electron") {
  throw "Expected electron shell, got $($desktopPlan.shell)"
}
if (-not $desktopPlan.electronDir.EndsWith("desktop\electron")) {
  throw "Unexpected Electron dir: $($desktopPlan.electronDir)"
}

$desktopSettingsDir = Join-Path ([System.IO.Path]::GetTempPath()) ("relief-desktop-settings-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $desktopSettingsDir | Out-Null
@{
  host = "127.0.0.2"
  backendPort = 8899
  frontendPort = 5299
  comfyUiEndpoint = "http://127.0.0.1:8199"
  workflowPath = "D:/ComfyUI/workflows/custom.json"
  stateDir = "D:/relief/state"
  logDir = "D:/relief/logs"
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $desktopSettingsDir "settings.json") -Encoding UTF8

$customDesktopPlan = & $desktopLauncher -DryRun -DesktopUserDataDir $desktopSettingsDir | ConvertFrom-Json
if ($customDesktopPlan.backendPort -ne 8899) {
  throw "Expected custom desktop backend port 8899, got $($customDesktopPlan.backendPort)"
}
if ($customDesktopPlan.frontendPort -ne 5299) {
  throw "Expected custom desktop frontend port 5299, got $($customDesktopPlan.frontendPort)"
}
if ($customDesktopPlan.comfyUiEndpoint -ne "http://127.0.0.1:8199") {
  throw "Expected custom ComfyUI endpoint, got $($customDesktopPlan.comfyUiEndpoint)"
}
if ($customDesktopPlan.frontendUrl -ne "http://127.0.0.2:5299/") {
  throw "Unexpected custom frontend URL: $($customDesktopPlan.frontendUrl)"
}

$desktopShortcutPlan = & $desktopInstaller -DryRun | ConvertFrom-Json
if (-not $desktopShortcutPlan.shortcutPath.EndsWith("Relief Story Agent Desktop.lnk")) {
  throw "Unexpected desktop app shortcut path: $($desktopShortcutPlan.shortcutPath)"
}

Write-Host "Desktop launcher smoke checks passed."
