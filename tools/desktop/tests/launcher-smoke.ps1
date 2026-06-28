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

$desktopShortcutPlan = & $desktopInstaller -DryRun | ConvertFrom-Json
if (-not $desktopShortcutPlan.shortcutPath.EndsWith("Relief Story Agent Desktop.lnk")) {
  throw "Unexpected desktop app shortcut path: $($desktopShortcutPlan.shortcutPath)"
}

Write-Host "Desktop launcher smoke checks passed."
