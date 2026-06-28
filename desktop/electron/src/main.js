const { app, BrowserWindow, shell } = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const path = require('path')

const host = process.env.RELIEF_DESKTOP_HOST || '127.0.0.1'
const backendPort = Number(process.env.RELIEF_BACKEND_PORT || 8891)
const frontendPort = Number(process.env.RELIEF_FRONTEND_PORT || 5173)
const backendUrl = `http://${host}:${backendPort}`
const frontendDevUrl = `http://${host}:${frontendPort}/`
const isDev = process.argv.includes('--dev') || !app.isPackaged

let backendProcess = null

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

function startBackend() {
  if (backendProcess) return

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
          ...process.env,
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
  if (!(await requestUrl(`${backendUrl}/api/health`))) {
    startBackend()
  }
  await waitForUrl(`${backendUrl}/api/health`)

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
    await win.loadURL(frontendDevUrl)
  } else {
    await win.loadFile(path.join(process.resourcesPath, 'frontend', 'index.html'))
  }
}

app.whenReady().then(createWindow)

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
