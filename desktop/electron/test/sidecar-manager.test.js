const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const { PassThrough } = require('node:stream')
const net = require('node:net')
const test = require('node:test')

const { SidecarManager, findAvailablePort } = require('../src/sidecar-manager')

class FakeChild extends EventEmitter {
  constructor() {
    super()
    this.stdout = new PassThrough()
    this.stderr = new PassThrough()
    this.killed = false
    this.pid = FakeChild.nextPid++
  }

  kill() {
    this.killed = true
    queueMicrotask(() => this.emit('exit', 0, null))
    return true
  }
}

FakeChild.nextPid = 30_000

async function makeManager(overrides = {}) {
  const userDataPath = await fs.mkdtemp(path.join(os.tmpdir(), 'relief-sidecar-'))
  const spawns = []
  const children = []
  const manager = new SidecarManager({
    host: '127.0.0.1',
    preferredPort: 8891,
    userDataPath,
    portResolver: async () => 19001,
    requestUrl: async () => true,
    spawnFn: (command, args, options) => {
      const child = new FakeChild()
      children.push(child)
      spawns.push({ command, args, options })
      return child
    },
    commandFactory: ({ host, port }) => ({
      command: 'python',
      args: ['-m', 'relief_story_agent.server', '--host', host, '--port', String(port)],
      cwd: 'D:/repo',
      env: { TEST_SECRET: 'secret' },
    }),
    processPlatform: 'linux',
    pollIntervalMs: 1,
    startupTimeoutMs: 50,
    ...overrides,
  })
  return { manager, spawns, children, userDataPath }
}

test('starts on a resolved free port and exposes an actual handshake', async () => {
  const { manager, spawns } = await makeManager()

  const status = await manager.start()

  assert.equal(status.status, 'running')
  assert.equal(status.port, 19001)
  assert.equal(status.backendUrl, 'http://127.0.0.1:19001')
  assert.deepEqual(spawns[0].args.slice(-4), [
    '--host',
    '127.0.0.1',
    '--port',
    '19001',
  ])
  assert.equal(spawns[0].options.windowsHide, true)
  assert.equal(spawns[0].options.env.TEST_SECRET, 'secret')
})

test('localhost port discovery notices a port occupied on 127.0.0.1', async () => {
  const occupied = net.createServer()
  await new Promise((resolve, reject) => {
    occupied.once('error', reject)
    occupied.listen(0, '127.0.0.1', resolve)
  })
  const address = occupied.address()
  const occupiedPort = typeof address === 'object' && address ? address.port : 0
  try {
    const resolved = await findAvailablePort('localhost', occupiedPort)
    assert.notEqual(resolved, occupiedPort)
    assert.ok(resolved > 0)
  } finally {
    await new Promise((resolve) => occupied.close(resolve))
  }
})

test('captures stdout and stderr in the desktop log', async () => {
  const { manager, children, userDataPath } = await makeManager()
  await manager.start()

  children[0].stdout.write('backend ready\n')
  children[0].stderr.write('diagnostic line\n')
  await new Promise((resolve) => setTimeout(resolve, 10))

  const log = await fs.readFile(path.join(userDataPath, 'logs', 'backend.log'), 'utf8')
  assert.match(log, /backend ready/)
  assert.match(log, /diagnostic line/)
})

test('restart stops the old process and starts a new process', async () => {
  const { manager, children, spawns } = await makeManager()
  await manager.start()

  const status = await manager.restart()

  assert.equal(children[0].killed, true)
  assert.equal(spawns.length, 2)
  assert.equal(status.status, 'running')
})

test('uses Windows process-tree termination when stopping the packaged sidecar', async () => {
  const terminatedPids = []
  const { manager, children } = await makeManager({
    processPlatform: 'win32',
    terminateProcessTree: async (child) => {
      terminatedPids.push(child.pid)
      child.kill()
    },
  })
  await manager.start()

  await manager.stop()

  assert.deepEqual(terminatedPids, [children[0].pid])
  assert.equal(children[0].killed, true)
})

test('serializes overlapping restarts so only one sidecar remains running', async () => {
  const { manager, children, spawns } = await makeManager({
    requestUrl: async () => {
      await new Promise((resolve) => setTimeout(resolve, 5))
      return true
    },
  })
  await manager.start()

  await Promise.all([
    manager.restart(),
    manager.restart(),
    manager.restart(),
  ])

  const runningChildren = children.filter((child) => !child.killed)
  assert.equal(spawns.length, 4)
  assert.equal(runningChildren.length, 1)
  assert.equal(manager.getStatus().status, 'running')
})

test('startup timeout kills the process and exposes the failure', async () => {
  const { manager, children } = await makeManager({
    requestUrl: async () => false,
    startupTimeoutMs: 5,
  })

  await assert.rejects(manager.start(), /failed to become healthy/)

  assert.equal(children[0].killed, true)
  assert.equal(manager.getStatus().status, 'failed')
  assert.match(manager.getStatus().lastError, /failed to become healthy/)
})
