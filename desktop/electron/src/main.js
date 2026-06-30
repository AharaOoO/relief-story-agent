const { app, BrowserWindow, shell, ipcMain, safeStorage } = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const path = require('path')
const fs = require('fs').promises

const host = process.env.RELIEF_DESKTOP_HOST || 'localhost'
const backendPort = Number(process.env.RELIEF_BACKEND_PORT || 8891)
const frontendPort = Number(process.env.RELIEF_FRONTEND_PORT || 5173)
const backendUrl = `http://${host}:${backendPort}`
const frontendDevUrl = `http://${host}:${frontendPort}/`
const isDev = process.argv.includes('--dev') || !app.isPackaged

let backendProcess = null
let frontendProcess = null

async function startFrontend() {
  if (frontendProcess) return

  if (isDev) {
    const repoRoot = path.resolve(__dirname, '../../..')
    frontendProcess = spawn(
      'npm',
      ['run', 'dev'],
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

async function loadSettings() {
  const settingsPath = path.join(app.getPath('userData'), 'settings.json')
  try {
    const data = await fs.readFile(settingsPath, 'utf8')
    const settings = JSON.parse(data)
    if (safeStorage.isEncryptionAvailable()) {
      for (const [key, value] of Object.entries(settings)) {
        if (key.endsWith('API_KEY') && value) {
          try {
            settings[key] = safeStorage.decryptString(Buffer.from(value, 'base64'))
          } catch (e) {
            console.error('Failed to decrypt', key, e)
          }
        }
      }
    }
    return settings
  } catch (err) {
    if (err.code !== 'ENOENT') {
      console.error('Error loading settings:', err)
    }
    return {}
  }
}

async function saveSettings(newSettings) {
  const settingsPath = path.join(app.getPath('userData'), 'settings.json')
  const current = await loadSettings()
  const settings = { ...current, ...newSettings }
  const toSave = { ...settings }
  
  if (safeStorage.isEncryptionAvailable()) {
    for (const [key, value] of Object.entries(toSave)) {
      if (key.endsWith('API_KEY') && value) {
        try {
          toSave[key] = safeStorage.encryptString(value).toString('base64')
        } catch (e) {
          console.error('Failed to encrypt', key, e)
        }
      }
    }
  }
  
  await fs.writeFile(settingsPath, JSON.stringify(toSave, null, 2), 'utf8')
  return settings
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

async function startBackend() {
  if (backendProcess) return

  const settings = await loadSettings()
  const env = { ...process.env, ...settings }

  if (isDev) {
    const repoRoot = path.resolve(__dirname, '../../..')
    const stateDir = path.join(repoRoot, 'relief_story_state')
    const modelConfig = path.join(
      repoRoot,
      'relief_story_agent',
      'examples',
      'model_config.local.example.json',
    )
    const pythonPath = process.env.PYTHONPATH
      ? `${repoRoot}${path.delimiter}${process.env.PYTHONPATH}`
      : repoRoot

    backendProcess = spawn(
      'python',
      [
        '-m',
        'relief_story_agent.server',
        '--host',
        host,
        '--port',
        String(backendPort),
        '--state-dir',
        stateDir,
        '--model-config',
        modelConfig,
        '--max-workers',
        '2',
        '--lease-seconds',
        '300',
        '--recovery-poll-seconds',
        '5',
      ],
      {
        cwd: repoRoot,
        env: {
          ...env,
          PYTHONPATH: pythonPath,
        },
        stdio: 'ignore',
        windowsHide: true,
      },
    )
    return
  }

  const sidecarPath = path.join(
    process.resourcesPath,
    'bin',
    'relief-story-agent-api.exe',
  )
  backendProcess = spawn(
    sidecarPath,
    [
      '--host',
      host,
      '--port',
      String(backendPort),
      '--state-dir',
      path.join(app.getPath('userData'), 'state'),
    ],
    {
      env,
      stdio: 'ignore',
      windowsHide: true,
    },
  )
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill()
  }
  backendProcess = null
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
      color: '#0a0a0a',
      symbolColor: '#f5f5f5',
      height: 36,
    } : false,
    backgroundColor: '#0a0a0a',
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

      if (!(await requestUrl(`${backendUrl}/api/health`))) {
        await startBackend()
      }
      const backendReady = await waitForUrl(`${backendUrl}/api/health`)
      if (!backendReady) throw new Error(`Backend failed to start at ${backendUrl}`)

      if (isDev) {
        await win.loadURL(frontendDevUrl)
      } else {
        await win.loadFile(path.join(process.resourcesPath, 'frontend', 'index.html'))
      }
    } catch (err) {
      console.error('Failed to boot services:', err)
      win.webContents.executeJavaScript(`
        document.querySelector('.text').innerText = 'Boot Failed: ${err.message}';
        document.querySelector('.spinner').style.borderColor = 'red';
        document.querySelector('.spinner').style.animation = 'none';
      `)
    }
  }

  bootServices()
}

app.whenReady().then(() => {
  ipcMain.handle('get-settings', async () => await loadSettings())
  ipcMain.handle('save-settings', async (event, settings) => await saveSettings(settings))
  ipcMain.handle('get-handshake', () => ({
    backendUrl,
    backendPort,
    platform: process.platform,
    version: app.getVersion()
  }))
  createWindow()
})

app.on('before-quit', () => {
  stopBackend()
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
