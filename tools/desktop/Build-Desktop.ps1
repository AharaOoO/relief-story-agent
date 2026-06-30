[CmdletBinding()]
param(
    [switch]$SkipInstaller,
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$SidecarDist = Join-Path $RepoRoot 'desktop\electron\sidecar\bin'
$SidecarExe = Join-Path $SidecarDist 'relief-story-agent-api.exe'
$PyInstallerWork = Join-Path $RepoRoot 'build\desktop-sidecar'
$EntryPoint = Join-Path $RepoRoot 'desktop\electron\sidecar\entry.py'
$BuildVenv = Join-Path $PyInstallerWork 'venv-py312'
$BuildPython = Join-Path $BuildVenv 'Scripts\python.exe'

function Invoke-DesktopPython {
    & py.exe -3.12 @args
    if ($LASTEXITCODE -ne 0) {
        throw 'Python 3.12 is required to build the desktop sidecar.'
    }
}

Push-Location $RepoRoot
try {
    Write-Host '[1/3] Building the offline frontend...'
    & npm.cmd --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }

    if (-not (Test-Path -LiteralPath $BuildPython)) {
        Write-Host 'Creating an isolated desktop build environment...'
        New-Item -ItemType Directory -Force -Path $PyInstallerWork | Out-Null
        Invoke-DesktopPython -m venv $BuildVenv
    }

    if (-not $SkipDependencyInstall) {
        Write-Host 'Installing sidecar build dependencies in the isolated environment...'
        & $BuildPython -m pip install --disable-pip-version-check --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw 'Build pip upgrade failed.' }
        & $BuildPython -m pip install --disable-pip-version-check pyinstaller $RepoRoot
        if ($LASTEXITCODE -ne 0) { throw 'Sidecar dependency installation failed.' }
    } elseif (-not ((& $BuildPython -c "import importlib.util; print('1' if importlib.util.find_spec('PyInstaller') else '0')") -eq '1')) {
        throw 'PyInstaller is missing from the isolated build environment.'
    }

    Write-Host '[2/3] Building the Python API sidecar...'
    New-Item -ItemType Directory -Force -Path $SidecarDist | Out-Null
    New-Item -ItemType Directory -Force -Path $PyInstallerWork | Out-Null
    if (Test-Path -LiteralPath $SidecarExe) {
        try {
            Remove-Item -LiteralPath $SidecarExe -Force
        }
        catch {
            throw 'The desktop API sidecar is still running. Close Relief Story Agent before rebuilding.'
        }
    }
    & $BuildPython -m PyInstaller `
        --clean `
        --noconfirm `
        --onefile `
        --name relief-story-agent-api `
        --distpath $SidecarDist `
        --workpath (Join-Path $PyInstallerWork 'work') `
        --specpath $PyInstallerWork `
        --paths $RepoRoot `
        $EntryPoint
    if ($LASTEXITCODE -ne 0) { throw 'Python sidecar build failed.' }

    if ($SkipInstaller) {
        Write-Host '[3/3] Installer build skipped.'
    } else {
        Write-Host '[3/3] Building the Windows installer...'
        & npm.cmd --prefix desktop/electron run dist
        if ($LASTEXITCODE -ne 0) { throw 'Electron installer build failed.' }
    }

    Write-Host 'Desktop build completed.' -ForegroundColor Green
    Write-Host "Sidecar: $SidecarDist"
    if (-not $SkipInstaller) {
        Write-Host "Installer: $(Join-Path $RepoRoot 'desktop\electron\release')"
    }
}
finally {
    Pop-Location
}
