const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const {
  createDefaultSettings,
  loadSettings,
  saveSettings,
  validateSettings,
} = require('./settings')
const {
  buildBackendLaunch,
  buildBackendUrl,
  buildFrontendDevUrl,
  buildUiOrigin,
} = require('./backend')

function makeUserDataDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'relief-desktop-settings-'))
}

test('creates desktop defaults from the user data directory', () => {
  const userDataDir = makeUserDataDir()
  const settings = createDefaultSettings(userDataDir)

  assert.equal(settings.host, '127.0.0.1')
  assert.equal(settings.backendPort, 8891)
  assert.equal(settings.frontendPort, 5173)
  assert.equal(settings.comfyUiEndpoint, 'http://127.0.0.1:8188')
  assert.equal(settings.workflowPath, 'D:/ComfyUI/workflows/ltx23_four_grid.json')
  assert.equal(settings.stateDir, path.join(userDataDir, 'state'))
  assert.equal(settings.logDir, path.join(userDataDir, 'logs'))
})

test('saves and loads user-edited desktop settings', () => {
  const userDataDir = makeUserDataDir()

  const saved = saveSettings(userDataDir, {
    backendPort: '8899',
    frontendPort: 5299,
    comfyUiEndpoint: 'http://192.168.31.8:8189/',
    workflowPath: 'D:/ComfyUI/custom/workflow.json',
    stateDir: 'D:/relief/state',
    logDir: 'D:/relief/logs',
  })
  const loaded = loadSettings(userDataDir)

  assert.deepEqual(loaded, saved)
  assert.equal(loaded.backendPort, 8899)
  assert.equal(loaded.frontendPort, 5299)
  assert.equal(loaded.comfyUiEndpoint, 'http://192.168.31.8:8189/')
})

test('rejects invalid ports and non-http endpoints', () => {
  const defaults = createDefaultSettings(makeUserDataDir())

  assert.throws(
    () => validateSettings({ ...defaults, backendPort: 80 }),
    /backendPort must be between 1024 and 65535/,
  )
  assert.throws(
    () => validateSettings({ ...defaults, frontendPort: 70000 }),
    /frontendPort must be between 1024 and 65535/,
  )
  assert.throws(
    () => validateSettings({ ...defaults, comfyUiEndpoint: 'file:///tmp/workflow' }),
    /comfyUiEndpoint must use http or https/,
  )
})

test('builds desktop URLs from editable settings', () => {
  const settings = {
    ...createDefaultSettings(makeUserDataDir()),
    host: '192.168.31.9',
    backendPort: 8899,
    frontendPort: 5299,
  }

  assert.equal(buildBackendUrl(settings), 'http://192.168.31.9:8899')
  assert.equal(buildFrontendDevUrl(settings), 'http://192.168.31.9:5299/')
  assert.equal(buildUiOrigin(settings), 'http://192.168.31.9:5299')
})

test('builds backend launch arguments from saved desktop settings', () => {
  const settings = {
    ...createDefaultSettings(makeUserDataDir()),
    host: '127.0.0.2',
    backendPort: 8899,
    frontendPort: 5299,
    comfyUiEndpoint: 'http://127.0.0.1:8199',
    stateDir: 'D:/relief/state',
  }

  const launch = buildBackendLaunch(settings, {
    isDev: true,
    repoRoot: 'D:/repo',
    modelConfigPath: 'D:/repo/relief_story_agent/examples/model_config.local.example.json',
    env: { PYTHONPATH: 'D:/existing' },
  })

  assert.equal(launch.command, 'python')
  assert.equal(launch.cwd, 'D:/repo')
  assert.deepEqual(launch.args.slice(0, 3), [
    '-m',
    'relief_story_agent.server',
    '--host',
  ])
  assert.ok(launch.args.includes('127.0.0.2'))
  assert.ok(launch.args.includes('8899'))
  assert.ok(launch.args.includes('--ui-origin'))
  assert.ok(launch.args.includes('http://127.0.0.2:5299'))
  assert.ok(launch.args.includes('--comfyui-endpoint'))
  assert.ok(launch.args.includes('http://127.0.0.1:8199'))
  assert.ok(launch.args.includes('--state-dir'))
  assert.ok(launch.args.includes('D:/relief/state'))
  assert.match(launch.env.PYTHONPATH, /^D:\/repo/)
})
