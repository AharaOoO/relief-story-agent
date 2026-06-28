[CmdletBinding()]
param(
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$LauncherPath = Join-Path $RepoRoot "tools\desktop\Start-ReliefStoryAgentDesktop.ps1"
$IconPath = Join-Path $RepoRoot "tools\desktop\assets\relief-story-agent.ico"
$IconInstaller = Join-Path $RepoRoot "tools\desktop\Install-Shortcut.ps1"
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Relief Story Agent Desktop.lnk"
$ShortcutArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$LauncherPath`""

function New-Shortcut {
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($ShortcutPath)
  $shortcut.TargetPath = "powershell.exe"
  $shortcut.Arguments = $ShortcutArguments
  $shortcut.WorkingDirectory = $RepoRoot
  $shortcut.IconLocation = $IconPath
  $shortcut.Description = "Launch Relief Story Agent as an Electron desktop client"
  $shortcut.Save()
}

if ($DryRun) {
  [ordered]@{
    repoRoot = $RepoRoot
    launcherPath = $LauncherPath
    shortcutPath = $ShortcutPath
    iconPath = $IconPath
    targetPath = "powershell.exe"
    arguments = $ShortcutArguments
  } | ConvertTo-Json -Depth 4
  exit 0
}

if (-not (Test-Path -LiteralPath $LauncherPath)) {
  throw "Desktop launcher not found: $LauncherPath"
}

if (-not (Test-Path -LiteralPath $IconPath)) {
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $IconInstaller
}

New-Shortcut

Write-Host "Created desktop client shortcut: $ShortcutPath" -ForegroundColor Green
