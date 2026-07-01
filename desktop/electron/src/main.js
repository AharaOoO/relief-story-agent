const {
  app,
  BrowserWindow,
  dialog,
  shell,
  ipcMain,
  safeStorage,
} = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const path = require('path')
const fs = require('fs').promises
const { CHANNELS } = require('./ipc-contract')
const { SettingsStore } = require('./settings-store')
const { SidecarManager, findAvailablePort } = require('./sidecar-manager')
const { createBackendCommand } = require('./backend-command')

const host = process.env.RELIEF_DESKTOP_HOST || '127.0.0.1'
const preferredBackendPort = Number(process.env.RELIEF_BACKEND_PORT || 8891)
const preferredFrontendPort = Number(process.env.RELIEF_FRONTEND_PORT || 5173)
const isDev = process.argv.includes('--dev') || !app.isPackaged

let frontendProcess = null
let frontendPort = preferredFrontendPort
let frontendDevUrl = `http://${host}:${frontendPort}/`
let settingsStore = null
let sidecarManager = null

async function startFrontend() {
  if (frontendProcess) return

  if (isDev) {
    frontendPort = await findAvailablePort(host, preferredFrontendPort)
    frontendDevUrl = `http://${host}:${frontendPort}/`
    const repoRoot = path.resolve(__dirname, '../../..')
    frontendProcess = spawn(
      'npm',
      ['run', 'dev', '--', '--host', host, '--port', String(frontendPort)],
      {
        cwd: path.join(repoRoot, 'frontend'),
        stdio: 'ignore',
        windowsHide: true,
        shell: true,
      }
    )
  }
}

function stopFrontend() {
  if (frontendProcess && !frontendProcess.killed) {
    frontendProcess.kill()
  }
  frontendProcess = null
}

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

function handshake() {
  const backend = sidecarManager?.getStatus() || {
    status: 'stopped',
    port: null,
    backendUrl: '',
    logPath: '',
    lastError: '',
  }
  return {
    backendUrl: backend.backendUrl,
    backendPort: backend.port,
    backendStatus: backend.status,
    backendLogPath: backend.logPath,
    backendLastError: backend.lastError,
    frontendPort: isDev ? frontendPort : null,
    platform: process.platform,
    version: app.getVersion(),
  }
}

async function restartBackend() {
  await sidecarManager.restart()
  return handshake()
}

function ownerWindow(event) {
  return BrowserWindow.fromWebContents(event.sender) || undefined
}

async function pickFile(event, options) {
  const result = await dialog.showOpenDialog(ownerWindow(event), {
    properties: ['openFile'],
    ...options,
  })
  if (result.canceled || !result.filePaths[0]) {
    return { canceled: true }
  }
  return { canceled: false, path: result.filePaths[0] }
}

function registerDesktopIpc() {
  ipcMain.handle(CHANNELS.getRuntimeConfig, () => settingsStore.getRuntimeConfig())
  ipcMain.handle(CHANNELS.saveRuntimeConfig, async (_event, config) => {
    const saved = await settingsStore.saveRuntimeConfig(config)
    const runtime = await restartBackend()
    return { config: saved, handshake: runtime }
  })
  ipcMain.handle(CHANNELS.getSecretStatus, () => settingsStore.getSecretStatus())
  ipcMain.handle(CHANNELS.saveSecret, async (_event, name, value) => {
    const status = await settingsStore.saveSecret(name, value)
    const runtime = await restartBackend()
    return { status, handshake: runtime }
  })
  ipcMain.handle(CHANNELS.deleteSecret, async (_event, name) => {
    const status = await settingsStore.deleteSecret(name)
    const runtime = await restartBackend()
    return { status, handshake: runtime }
  })
  ipcMain.handle(CHANNELS.pickWorkflow, (event) => pickFile(event, {
    title: '选择 ComfyUI 工作流',
    filters: [{ name: 'ComfyUI workflow', extensions: ['json'] }],
  }))
  ipcMain.handle(CHANNELS.pickScript, async (event) => {
    const selected = await pickFile(event, {
      title: '导入剧本或创作要求',
      filters: [{ name: 'Story files', extensions: ['txt', 'md', 'json'] }],
    })
    if (selected.canceled) return selected
    return {
      ...selected,
      name: path.basename(selected.path),
      content: await fs.readFile(selected.path, 'utf8'),
    }
  })
  ipcMain.handle(CHANNELS.pickDirectory, async (event) => {
    const result = await dialog.showOpenDialog(ownerWindow(event), {
      title: '选择目录',
      properties: ['openDirectory', 'createDirectory'],
    })
    return result.canceled || !result.filePaths[0]
      ? { canceled: true }
      : { canceled: false, path: result.filePaths[0] }
  })
  ipcMain.handle(CHANNELS.openPath, async (_event, targetPath) => {
    if (typeof targetPath !== 'string' || !path.isAbsolute(targetPath)) {
      throw new Error('openPath requires an absolute local path')
    }
    const error = await shell.openPath(targetPath)
    if (error) throw new Error(error)
    return { opened: true }
  })
  ipcMain.handle(CHANNELS.restartBackend, restartBackend)
  ipcMain.handle(CHANNELS.getHandshake, handshake)
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1040,
    minHeight: 720,
    title: 'Relief Story Agent',
    frame: false,
    titleBarStyle: 'hidden',
    titleBarOverlay: process.platform === 'win32' ? {
      color: '#f7f9fc',
      symbolColor: '#252832',
      height: 36,
    } : false,
    backgroundColor: '#f7f9fc',
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
  
  if (isDev && process.env.RELIEF_OPEN_DEVTOOLS === '1') {
    win.webContents.openDevTools()
  }

  // Load splash screen immediately
  await win.loadFile(path.join(__dirname, 'splash.html'))

  // Start background services asynchronously
  const bootServices = async () => {
    try {
      if (isDev) {
        await startFrontend()
        const frontendReady = await waitForUrl(frontendDevUrl)
        if (!frontendReady) throw new Error(`Frontend failed to start at ${frontendDevUrl}`)
      }

      await sidecarManager.start()

      if (isDev) {
        await win.loadURL(frontendDevUrl)
      } else {
        await win.loadFile(path.join(process.resourcesPath, 'frontend', 'index.html'))
      }
    } catch (err) {
      console.error('Failed to boot services:', err)
      const message = JSON.stringify(`启动失败：${err.message}`)
      win.webContents.executeJavaScript(`
        document.querySelector('.text').innerText = ${message};
        document.querySelector('.spinner').style.borderColor = 'red';
        document.querySelector('.spinner').style.animation = 'none';
      `)
    }
  }

  bootServices()
}

app.whenReady().then(() => {
  settingsStore = new SettingsStore({
    userDataPath: app.getPath('userData'),
    safeStorage,
  })
  const repoRoot = path.resolve(__dirname, '../../..')
  sidecarManager = new SidecarManager({
    host,
    preferredPort: preferredBackendPort,
    userDataPath: app.getPath('userData'),
    spawnFn: spawn,
    requestUrl,
    commandFactory: async ({ host: sidecarHost, port }) => {
      const [environment, runtimeConfig] = await Promise.all([
        settingsStore.getEnvironment(),
        settingsStore.getRuntimeConfig(),
      ])
      return createBackendCommand({
        isDev,
        repoRoot,
        resourcesPath: process.resourcesPath,
        userDataPath: app.getPath('userData'),
        host: sidecarHost,
        port,
        uiOrigin: isDev ? frontendDevUrl.replace(/\/$/, '') : 'null',
        extraCorsOrigins: isDev
          ? [`http://localhost:${frontendPort}`]
          : [],
        environment,
        runtimeConfig,
        processEnvironment: process.env,
      })
    },
  })
  registerDesktopIpc()
  createWindow()
})

app.on('before-quit', () => {
  void sidecarManager?.stop()
  stopFrontend()
})

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
