[CmdletBinding()]
param(
  [switch]$DryRun,
  [switch]$StartMenu
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$LauncherPath = Join-Path $RepoRoot "tools\desktop\Start-ReliefStoryAgent.ps1"
$AssetsDir = Join-Path $RepoRoot "tools\desktop\assets"
$IconPath = Join-Path $AssetsDir "relief-story-agent.ico"
$PreviewPngPath = Join-Path $AssetsDir "relief-story-agent-icon-preview.png"
$DesktopShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Relief Story Agent.lnk"
$StartMenuShortcutPath = Join-Path ([Environment]::GetFolderPath("Programs")) "Relief Story Agent.lnk"
$ShortcutArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$LauncherPath`""

function New-RoundedRectanglePath {
  param(
    [float]$X,
    [float]$Y,
    [float]$Width,
    [float]$Height,
    [float]$Radius
  )

  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  $diameter = $Radius * 2
  $path.AddArc($X, $Y, $diameter, $diameter, 180, 90)
  $path.AddArc($X + $Width - $diameter, $Y, $diameter, $diameter, 270, 90)
  $path.AddArc($X + $Width - $diameter, $Y + $Height - $diameter, $diameter, $diameter, 0, 90)
  $path.AddArc($X, $Y + $Height - $diameter, $diameter, $diameter, 90, 90)
  $path.CloseFigure()
  return $path
}

function Write-ReliefStoryIcon {
  param(
    [string]$PngPath,
    [string]$IcoPath
  )

  Add-Type -AssemblyName System.Drawing

  $bitmap = New-Object System.Drawing.Bitmap 256, 256
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

  $cream = [System.Drawing.ColorTranslator]::FromHtml("#fff2df")
  $gold = [System.Drawing.ColorTranslator]::FromHtml("#ffbf00")
  $chocolate = [System.Drawing.ColorTranslator]::FromHtml("#6b3e28")
  $blue = [System.Drawing.ColorTranslator]::FromHtml("#254474")
  $mint = [System.Drawing.ColorTranslator]::FromHtml("#3dc17a")

  $creamBrush = New-Object System.Drawing.SolidBrush $cream
  $goldBrush = New-Object System.Drawing.SolidBrush $gold
  $chocolateBrush = New-Object System.Drawing.SolidBrush $chocolate
  $blueBrush = New-Object System.Drawing.SolidBrush $blue
  $mintBrush = New-Object System.Drawing.SolidBrush $mint
  $borderPen = New-Object System.Drawing.Pen $chocolate, 9
  $font = New-Object System.Drawing.Font "Impact", 112, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
  $smallFont = New-Object System.Drawing.Font "Arial", 28, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)

  try {
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $outer = New-RoundedRectanglePath -X 14 -Y 14 -Width 228 -Height 228 -Radius 38
    $graphics.FillPath($creamBrush, $outer)
    $graphics.DrawPath($borderPen, $outer)

    $blueStrip = New-RoundedRectanglePath -X 36 -Y 38 -Width 54 -Height 180 -Radius 24
    $graphics.FillPath($blueBrush, $blueStrip)

    $goldPanel = New-RoundedRectanglePath -X 78 -Y 44 -Width 138 -Height 130 -Radius 28
    $graphics.FillPath($goldBrush, $goldPanel)

    $graphics.FillEllipse($mintBrush, 174, 162, 44, 44)
    $graphics.DrawString("R", $font, $chocolateBrush, 91, 45)
    $graphics.DrawString("AI", $smallFont, $creamBrush, 42, 69)

    $bitmap.Save($PngPath, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $font.Dispose()
    $smallFont.Dispose()
    $borderPen.Dispose()
    $creamBrush.Dispose()
    $goldBrush.Dispose()
    $chocolateBrush.Dispose()
    $blueBrush.Dispose()
    $mintBrush.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
  }

  $pngBytes = [System.IO.File]::ReadAllBytes($PngPath)
  $memory = New-Object System.IO.MemoryStream
  $writer = New-Object System.IO.BinaryWriter $memory

  try {
    $writer.Write([UInt16]0)
    $writer.Write([UInt16]1)
    $writer.Write([UInt16]1)
    $writer.Write([Byte]0)
    $writer.Write([Byte]0)
    $writer.Write([Byte]0)
    $writer.Write([Byte]0)
    $writer.Write([UInt16]1)
    $writer.Write([UInt16]32)
    $writer.Write([UInt32]$pngBytes.Length)
    $writer.Write([UInt32]22)
    $writer.Write($pngBytes)
    [System.IO.File]::WriteAllBytes($IcoPath, $memory.ToArray())
  } finally {
    $writer.Dispose()
    $memory.Dispose()
  }
}

function New-Shortcut {
  param(
    [string]$ShortcutPath
  )

  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($ShortcutPath)
  $shortcut.TargetPath = "powershell.exe"
  $shortcut.Arguments = $ShortcutArguments
  $shortcut.WorkingDirectory = $RepoRoot
  $shortcut.IconLocation = $IconPath
  $shortcut.Description = "Launch Relief Story Agent local API and desktop UI"
  $shortcut.Save()
}

if ($DryRun) {
  [ordered]@{
    repoRoot = $RepoRoot
    launcherPath = $LauncherPath
    shortcutPath = $DesktopShortcutPath
    startMenuShortcutPath = $StartMenuShortcutPath
    iconPath = $IconPath
    previewPngPath = $PreviewPngPath
    targetPath = "powershell.exe"
    arguments = $ShortcutArguments
  } | ConvertTo-Json -Depth 4
  exit 0
}

if (-not (Test-Path -LiteralPath $LauncherPath)) {
  throw "Launcher not found: $LauncherPath"
}

New-Item -ItemType Directory -Force -Path $AssetsDir | Out-Null
Write-ReliefStoryIcon -PngPath $PreviewPngPath -IcoPath $IconPath
New-Shortcut -ShortcutPath $DesktopShortcutPath

if ($StartMenu) {
  New-Shortcut -ShortcutPath $StartMenuShortcutPath
}

Write-Host "Created shortcut: $DesktopShortcutPath" -ForegroundColor Green
Write-Host "Icon: $IconPath" -ForegroundColor Cyan
