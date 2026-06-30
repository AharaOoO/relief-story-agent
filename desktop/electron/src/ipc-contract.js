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

function createDesktopBridge(invoke, platform) {
  return {
    platform,
    shell: 'electron',
    getRuntimeConfig: () => invoke(CHANNELS.getRuntimeConfig),
    saveRuntimeConfig: (config) => invoke(CHANNELS.saveRuntimeConfig, config),
    getSecretStatus: () => invoke(CHANNELS.getSecretStatus),
    saveSecret: (name, value) => invoke(CHANNELS.saveSecret, name, value),
    deleteSecret: (name) => invoke(CHANNELS.deleteSecret, name),
    pickWorkflow: () => invoke(CHANNELS.pickWorkflow),
    pickScript: () => invoke(CHANNELS.pickScript),
    pickDirectory: () => invoke(CHANNELS.pickDirectory),
    openPath: (targetPath) => invoke(CHANNELS.openPath, targetPath),
    restartBackend: () => invoke(CHANNELS.restartBackend),
    getHandshake: () => invoke(CHANNELS.getHandshake),
  }
}

module.exports = {
  CHANNELS,
  createDesktopBridge,
}

