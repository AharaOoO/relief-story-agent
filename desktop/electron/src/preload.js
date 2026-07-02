const { contextBridge, ipcRenderer, webUtils } = require('electron')

// Sandboxed preload scripts cannot import local CommonJS modules. Keep this
// explicit allowlist in sync with ipc-contract.js; no generic IPC is exposed.
const CHANNELS = Object.freeze({
  getRuntimeConfig: 'relief:desktop:get-runtime-config',
  saveRuntimeConfig: 'relief:desktop:save-runtime-config',
  getSecretStatus: 'relief:desktop:get-secret-status',
  saveSecret: 'relief:desktop:save-secret',
  deleteSecret: 'relief:desktop:delete-secret',
  pickWorkflow: 'relief:desktop:pick-workflow',
  pickScript: 'relief:desktop:pick-script',
  pickDirectory: 'relief:desktop:pick-directory',
  openPath: 'relief:desktop:open-path',
  restartBackend: 'relief:desktop:restart-backend',
  getHandshake: 'relief:desktop:get-handshake',
})

contextBridge.exposeInMainWorld('reliefDesktop', {
  platform: process.platform,
  shell: 'electron',
  getRuntimeConfig: () => ipcRenderer.invoke(CHANNELS.getRuntimeConfig),
  saveRuntimeConfig: (config) => ipcRenderer.invoke(CHANNELS.saveRuntimeConfig, config),
  getSecretStatus: () => ipcRenderer.invoke(CHANNELS.getSecretStatus),
  saveSecret: (name, value) => ipcRenderer.invoke(CHANNELS.saveSecret, name, value),
  deleteSecret: (name) => ipcRenderer.invoke(CHANNELS.deleteSecret, name),
  pickWorkflow: () => ipcRenderer.invoke(CHANNELS.pickWorkflow),
  pickScript: () => ipcRenderer.invoke(CHANNELS.pickScript),
  pickDirectory: () => ipcRenderer.invoke(CHANNELS.pickDirectory),
  getPathForFile: (file) => webUtils.getPathForFile(file),
  openPath: (targetPath) => ipcRenderer.invoke(CHANNELS.openPath, targetPath),
  restartBackend: () => ipcRenderer.invoke(CHANNELS.restartBackend),
  getHandshake: () => ipcRenderer.invoke(CHANNELS.getHandshake),
})
