const { app, BrowserWindow, ipcMain, shell } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const http = require('http')
const path = require('path')

const {
  buildBackendLaunch,
  buildBackendUrl,
  buildFrontendDevUrl,
  buildUiOrigin,
} = require('./backend')
const {
  createDefaultSettings,
  getSettingsFilePath,
  loadSettings,
  saveSettings,
} = require('./settings')

const isDev = process.argv.includes('--dev') || !app.isPackaged

let backendProcess = null
let currentSettings = null

function requestUrl(url) {
  return new Promise((resolve) => {
    const request = http.get(url, (response) => {
      response.resume()
      resolve(response.statusCode >= 200 && response.statusCode < 500)
    })

    request.on('error', () => resolve(false))
    request.setTimeout(1500, () => {
      request.destroy()
      resolve(false)
    })
  })
}

async function waitForUrl(url, timeoutMs = 45_000) {
  const startedAt = Date.now()

  while (Date.now() - startedAt < timeoutMs) {
    if (await requestUrl(url)) {
      return true
    }
    await new Promise((resolve) => setTimeout(resolve, 750))
  }

  return false
}

function getUserDataDir() {
  return process.env.RELIEF_DESKTOP_USER_DATA_DIR || app.getPath('userData')
}

function getRepoRoot() {
  return path.resolve(__dirname, '../../..')
}

function getModelConfigPath() {
  return path.join(
    getRepoRoot(),
    'relief_story_agent',
    'examples',
    'model_config.local.example.json',
  )
}

function loadCurrentSettings() {
  currentSettings = loadSettings(getUserDataDir())
  return currentSettings
}

function getDesktopState(settings = currentSettings || loadCurrentSettings()) {
  return {
    platform: process.platform,
    shell: 'electron',
    isDev,
    settings,
    settingsPath: getSettingsFilePath(getUserDataDir()),
    backendUrl: buildBackendUrl(settings),
    frontendDevUrl: buildFrontendDevUrl(settings),
    uiOrigin: buildUiOrigin(settings),
    backendRunning: Boolean(backendProcess && !backendProcess.killed),
    backendPid: backendProcess && !backendProcess.killed ? backendProcess.pid : null,
  }
}

function startBackend(settings = loadCurrentSettings()) {
  if (backendProcess && !backendProcess.killed) return

  const launch = buildBackendLaunch(settings, {
    isDev,
    repoRoot: getRepoRoot(),
    resourcesPath: process.resourcesPath,
    modelConfigPath: getModelConfigPath(),
    env: process.env,
  })
  const child = spawn(launch.command, launch.args, {
    cwd: launch.cwd,
    env: launch.env,
    stdio: 'ignore',
    windowsHide: true,
  })
  backendProcess = child
  child.once('exit', () => {
    if (backendProcess === child) {
      backendProcess = null
    }
  })
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill()
  }
  backendProcess = null
}

async function restartBackend() {
  stopBackend()
  await new Promise((resolve) => setTimeout(resolve, 250))
  const settings = loadCurrentSettings()
  startBackend(settings)
  await waitForUrl(`${buildBackendUrl(settings)}/api/health`)
  return getDesktopState(settings)
}

function registerIpcHandlers() {
  ipcMain.handle('relief:desktop:get-state', () => {
    const settings = loadCurrentSettings()
    return getDesktopState(settings)
  })

  ipcMain.handle('relief:desktop:save-settings', (_event, input) => {
    currentSettings = saveSettings(getUserDataDir(), input)
    return getDesktopState(currentSettings)
  })

  ipcMain.handle('relief:desktop:reset-settings', () => {
    currentSettings = saveSettings(
      getUserDataDir(),
      createDefaultSettings(getUserDataDir()),
    )
    return getDesktopState(currentSettings)
  })

  ipcMain.handle('relief:desktop:restart-backend', () => restartBackend())

  ipcMain.handle('relief:desktop:open-logs', async () => {
    const settings = loadCurrentSettings()
    fs.mkdirSync(settings.logDir, { recursive: true })
    const error = await shell.openPath(settings.logDir)
    return {
      opened: error === '',
      path: settings.logDir,
      error: error || null,
    }
  })
}

async function ensureBackendReady(settings) {
  const backendHealthUrl = `${buildBackendUrl(settings)}/api/health`
  if (!(await requestUrl(backendHealthUrl))) {
    startBackend(settings)
  }
  await waitForUrl(backendHealthUrl)
}

async function createWindow() {
  const settings = loadCurrentSettings()
  await ensureBackendReady(settings)

  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1040,
    minHeight: 720,
    title: 'Relief Story Agent',
    backgroundColor: '#fff2df',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.setMenuBarVisibility(false)
  win.once('ready-to-show', () => win.show())
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  if (isDev) {
    await win.loadURL(buildFrontendDevUrl(settings))
  } else {
    await win.loadFile(path.join(process.resourcesPath, 'frontend', 'index.html'))
  }
}

app.whenReady().then(() => {
  registerIpcHandlers()
  return createWindow()
})

app.on('before-quit', stopBackend)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})
