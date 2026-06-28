const fs = require('fs')
const path = require('path')

const SETTINGS_FILE_NAME = 'settings.json'
const DEFAULT_WORKFLOW_PATH = 'D:/ComfyUI/workflows/ltx23_four_grid.json'

function getSettingsFilePath(userDataDir) {
  return path.join(userDataDir, SETTINGS_FILE_NAME)
}

function createDefaultSettings(userDataDir) {
  return {
    host: process.env.RELIEF_DESKTOP_HOST || '127.0.0.1',
    backendPort: Number(process.env.RELIEF_BACKEND_PORT || 8891),
    frontendPort: Number(process.env.RELIEF_FRONTEND_PORT || 5173),
    comfyUiEndpoint:
      process.env.RELIEF_COMFYUI_ENDPOINT || 'http://127.0.0.1:8188',
    workflowPath: process.env.RELIEF_WORKFLOW_PATH || DEFAULT_WORKFLOW_PATH,
    stateDir: path.join(userDataDir, 'state'),
    logDir: path.join(userDataDir, 'logs'),
  }
}

function pickSettings(input) {
  const picked = {}
  for (const key of [
    'host',
    'backendPort',
    'frontendPort',
    'comfyUiEndpoint',
    'workflowPath',
    'stateDir',
    'logDir',
  ]) {
    if (Object.prototype.hasOwnProperty.call(input, key)) {
      picked[key] = input[key]
    }
  }
  return picked
}

function normalizeRequiredString(value, key) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`${key} must be a non-empty string`)
  }
  return value.trim()
}

function normalizePort(value, key) {
  const port = Number(value)
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    throw new Error(`${key} must be between 1024 and 65535`)
  }
  return port
}

function normalizeHttpUrl(value, key) {
  const urlText = normalizeRequiredString(value, key)
  let url
  try {
    url = new URL(urlText)
  } catch {
    throw new Error(`${key} must be a valid URL`)
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error(`${key} must use http or https`)
  }
  return urlText
}

function validateSettings(input) {
  return {
    host: normalizeRequiredString(input.host, 'host'),
    backendPort: normalizePort(input.backendPort, 'backendPort'),
    frontendPort: normalizePort(input.frontendPort, 'frontendPort'),
    comfyUiEndpoint: normalizeHttpUrl(input.comfyUiEndpoint, 'comfyUiEndpoint'),
    workflowPath: normalizeRequiredString(input.workflowPath, 'workflowPath'),
    stateDir: normalizeRequiredString(input.stateDir, 'stateDir'),
    logDir: normalizeRequiredString(input.logDir, 'logDir'),
  }
}

function loadSettings(userDataDir) {
  const defaults = createDefaultSettings(userDataDir)
  const settingsFile = getSettingsFilePath(userDataDir)

  if (!fs.existsSync(settingsFile)) {
    return validateSettings(defaults)
  }

  const saved = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  return validateSettings({
    ...defaults,
    ...pickSettings(saved),
  })
}

function saveSettings(userDataDir, input) {
  const settingsFile = getSettingsFilePath(userDataDir)
  const current = fs.existsSync(settingsFile)
    ? loadSettings(userDataDir)
    : createDefaultSettings(userDataDir)
  const settings = validateSettings({
    ...current,
    ...pickSettings(input),
  })

  fs.mkdirSync(userDataDir, { recursive: true })
  fs.mkdirSync(settings.stateDir, { recursive: true })
  fs.mkdirSync(settings.logDir, { recursive: true })

  const tempFile = `${settingsFile}.${process.pid}.tmp`
  fs.writeFileSync(tempFile, `${JSON.stringify(settings, null, 2)}\n`, 'utf8')
  fs.renameSync(tempFile, settingsFile)

  return settings
}

module.exports = {
  DEFAULT_WORKFLOW_PATH,
  SETTINGS_FILE_NAME,
  createDefaultSettings,
  getSettingsFilePath,
  loadSettings,
  saveSettings,
  validateSettings,
}
