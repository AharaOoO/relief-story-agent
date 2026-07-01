const fs = require('node:fs/promises')
const path = require('node:path')

const ALLOWED_SECRET_NAMES = Object.freeze([
  'RUNNINGHUB_CN_API_KEY',
  'RUNNINGHUB_AI_API_KEY',
  'RUNNINGHUB_CN_SHARED_API_KEY',
  'RUNNINGHUB_AI_SHARED_API_KEY',
  'GEMINI_API_KEY',
  'DEEPSEEK_API_KEY',
  'OPENAI_API_KEY',
  'IMAGE_API_KEY',
])

class SettingsStore {
  constructor({ userDataPath, safeStorage, fsModule = fs }) {
    this.userDataPath = userDataPath
    this.safeStorage = safeStorage
    this.fs = fsModule
    this.settingsPath = path.join(userDataPath, 'settings.json')
  }

  async getRuntimeConfig() {
    const settings = await this._load()
    return { ...settings.runtime }
  }

  async saveRuntimeConfig(patch) {
    if (!patch || typeof patch !== 'object' || Array.isArray(patch)) {
      throw new TypeError('runtime config patch must be an object')
    }
    const secretKeys = Object.keys(patch).filter(
      (key) => ALLOWED_SECRET_NAMES.includes(key) || key.endsWith('API_KEY'),
    )
    if (secretKeys.length) {
      throw new Error('runtime config cannot contain secrets')
    }
    const settings = await this._load()
    settings.runtime = { ...settings.runtime, ...patch }
    await this._save(settings)
    return { ...settings.runtime }
  }

  async getSecretStatus() {
    const settings = await this._load()
    const status = {}
    for (const name of ALLOWED_SECRET_NAMES) {
      const encrypted = settings.secrets[name]
      if (!encrypted) {
        status[name] = { configured: false, masked: '' }
        continue
      }
      let masked = '••••'
      try {
        const value = this._decrypt(encrypted)
        masked += value.slice(-4)
      } catch {
        masked += '????'
      }
      status[name] = { configured: true, masked }
    }
    return status
  }

  async saveSecret(name, value) {
    this._assertSecretName(name)
    if (typeof value !== 'string' || !value.trim()) {
      throw new Error('desktop secret value must be a non-empty string')
    }
    if (!this.safeStorage.isEncryptionAvailable()) {
      throw new Error('secure desktop storage is unavailable')
    }
    const settings = await this._load()
    settings.secrets[name] = this.safeStorage
      .encryptString(value.trim())
      .toString('base64')
    await this._save(settings)
    return (await this.getSecretStatus())[name]
  }

  async deleteSecret(name) {
    this._assertSecretName(name)
    const settings = await this._load()
    delete settings.secrets[name]
    await this._save(settings)
    return { configured: false, masked: '' }
  }

  async getEnvironment() {
    const settings = await this._load()
    const environment = {}
    for (const name of ALLOWED_SECRET_NAMES) {
      const encrypted = settings.secrets[name]
      if (encrypted) {
        environment[name] = this._decrypt(encrypted)
      }
    }
    return environment
  }

  _assertSecretName(name) {
    if (!ALLOWED_SECRET_NAMES.includes(name)) {
      throw new Error(`${name} is not an allowed desktop secret`)
    }
  }

  _decrypt(value) {
    if (!this.safeStorage.isEncryptionAvailable()) {
      throw new Error('secure desktop storage is unavailable')
    }
    return this.safeStorage.decryptString(Buffer.from(value, 'base64'))
  }

  async _load() {
    try {
      const raw = JSON.parse(await this.fs.readFile(this.settingsPath, 'utf8'))
      if (raw.version === 1 && raw.runtime && raw.secrets) {
        return {
          version: 1,
          runtime: { ...raw.runtime },
          secrets: { ...raw.secrets },
        }
      }
      return this._migrateLegacy(raw)
    } catch (error) {
      if (error.code === 'ENOENT') {
        return { version: 1, runtime: {}, secrets: {} }
      }
      throw error
    }
  }

  _migrateLegacy(raw) {
    const runtime = {}
    const secrets = {}
    for (const [key, value] of Object.entries(raw || {})) {
      if (ALLOWED_SECRET_NAMES.includes(key)) {
        if (value) secrets[key] = value
      } else {
        runtime[key] = value
      }
    }
    return { version: 1, runtime, secrets }
  }

  async _save(settings) {
    await this.fs.mkdir(this.userDataPath, { recursive: true })
    const tempPath = `${this.settingsPath}.${process.pid}.${Date.now()}.tmp`
    await this.fs.writeFile(
      tempPath,
      JSON.stringify(settings, null, 2),
      'utf8',
    )
    await this.fs.rename(tempPath, this.settingsPath)
  }
}

module.exports = {
  ALLOWED_SECRET_NAMES,
  SettingsStore,
}
