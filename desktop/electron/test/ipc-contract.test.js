const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const {
  CHANNELS,
  createDesktopBridge,
} = require('../src/ipc-contract')

test('renderer bridge exposes only the approved desktop operations', async () => {
  const calls = []
  const bridge = createDesktopBridge(
    (channel, ...args) => {
      calls.push([channel, ...args])
      return Promise.resolve({ ok: true })
    },
    'win32',
  )

  assert.deepEqual(Object.keys(bridge).sort(), [
    'deleteSecret',
    'getHandshake',
    'getPathForFile',
    'getRuntimeConfig',
    'getSecretStatus',
    'openPath',
    'pickDirectory',
    'pickScript',
    'pickWorkflow',
    'platform',
    'restartBackend',
    'saveRuntimeConfig',
    'saveSecret',
    'shell',
  ])

  await bridge.saveSecret('OPENAI_API_KEY', 'secret')
  await bridge.pickWorkflow()
  await bridge.openPath('D:/relief/logs')

  assert.deepEqual(calls, [
    [CHANNELS.saveSecret, 'OPENAI_API_KEY', 'secret'],
    [CHANNELS.pickWorkflow],
    [CHANNELS.openPath, 'D:/relief/logs'],
  ])
})

test('legacy plaintext settings methods are not part of the contract', () => {
  const bridge = createDesktopBridge(() => Promise.resolve(), 'win32')

  assert.equal(bridge.getSettings, undefined)
  assert.equal(bridge.saveSettings, undefined)
})

test('sandboxed preload does not import local CommonJS modules', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'src', 'preload.js'), 'utf8')
  assert.doesNotMatch(source, /require\(['"]\.\//)
  assert.match(source, /contextBridge\.exposeInMainWorld/)
  assert.match(source, /webUtils\.getPathForFile/)
})

test('desktop shell prevents multiple clients from sharing one state directory', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'src', 'main.js'), 'utf8')

  assert.match(source, /app\.requestSingleInstanceLock\(\)/)
  assert.match(source, /second-instance/)
})
