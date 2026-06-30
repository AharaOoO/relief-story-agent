const fs = require('node:fs/promises')
const net = require('node:net')
const path = require('node:path')

function findAvailablePort(host, preferredPort) {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.unref()
    server.once('error', (error) => {
      if (error.code !== 'EADDRINUSE') {
        reject(error)
        return
      }
      const fallback = net.createServer()
      fallback.unref()
      fallback.once('error', reject)
      fallback.listen(0, host, () => {
        const address = fallback.address()
        const port = typeof address === 'object' && address ? address.port : 0
        fallback.close(() => resolve(port))
      })
    })
    server.listen(preferredPort, host, () => {
      server.close(() => resolve(preferredPort))
    })
  })
}

class SidecarManager {
  constructor({
    host,
    preferredPort,
    userDataPath,
    spawnFn,
    commandFactory,
    requestUrl,
    portResolver = (port) => findAvailablePort(host, port),
    startupTimeoutMs = 45_000,
    pollIntervalMs = 250,
  }) {
    this.host = host
    this.preferredPort = preferredPort
    this.userDataPath = userDataPath
    this.spawnFn = spawnFn
    this.commandFactory = commandFactory
    this.requestUrl = requestUrl
    this.portResolver = portResolver
    this.startupTimeoutMs = startupTimeoutMs
    this.pollIntervalMs = pollIntervalMs
    this.child = null
    this.port = null
    this.status = 'stopped'
    this.lastError = ''
    this.logPath = path.join(userDataPath, 'logs', 'backend.log')
  }

  getStatus() {
    return {
      status: this.status,
      host: this.host,
      port: this.port,
      backendUrl: this.port ? `http://${this.host}:${this.port}` : '',
      logPath: this.logPath,
      lastError: this.lastError,
    }
  }

  async start() {
    if (this.child && this.status === 'running') {
      return this.getStatus()
    }
    this.status = 'starting'
    this.lastError = ''
    this.port = await this.portResolver(this.preferredPort)
    const command = await this.commandFactory({
      host: this.host,
      port: this.port,
    })
    await fs.mkdir(path.dirname(this.logPath), { recursive: true })
    this.child = this.spawnFn(command.command, command.args, {
      cwd: command.cwd,
      env: command.env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      shell: Boolean(command.shell),
    })
    this._captureLogs(this.child)
    this._observeExit(this.child)

    const healthUrl = `http://${this.host}:${this.port}/api/health`
    const startedAt = Date.now()
    while (Date.now() - startedAt <= this.startupTimeoutMs) {
      if (await this.requestUrl(healthUrl)) {
        this.status = 'running'
        return this.getStatus()
      }
      await new Promise((resolve) => setTimeout(resolve, this.pollIntervalMs))
    }
    const message = `Backend failed to become healthy at ${healthUrl}`
    await this.stop()
    this.status = 'failed'
    this.lastError = message
    throw new Error(message)
  }

  async stop() {
    const child = this.child
    if (!child) {
      this.status = 'stopped'
      return this.getStatus()
    }
    this.status = 'stopping'
    await new Promise((resolve) => {
      let settled = false
      const finish = () => {
        if (settled) return
        settled = true
        resolve()
      }
      child.once('exit', finish)
      child.kill()
      setTimeout(finish, 2_000)
    })
    this.child = null
    this.status = 'stopped'
    return this.getStatus()
  }

  async restart() {
    await this.stop()
    return this.start()
  }

  _captureLogs(child) {
    const append = (source, chunk) => {
      const line = `[${new Date().toISOString()}] [${source}] ${chunk.toString()}`
      fs.appendFile(this.logPath, line, 'utf8').catch(() => {})
    }
    child.stdout?.on('data', (chunk) => append('stdout', chunk))
    child.stderr?.on('data', (chunk) => append('stderr', chunk))
  }

  _observeExit(child) {
    child.once('error', (error) => {
      this.lastError = error.message
      this.status = 'failed'
    })
    child.once('exit', (code, signal) => {
      if (this.child === child) this.child = null
      if (this.status === 'stopping' || this.status === 'stopped') return
      if (this.status === 'failed') return
      this.status = code === 0 ? 'stopped' : 'failed'
      if (code !== 0) {
        this.lastError = `Backend exited with code ${code}${signal ? ` (${signal})` : ''}`
      }
    })
  }
}

module.exports = {
  SidecarManager,
  findAvailablePort,
}

