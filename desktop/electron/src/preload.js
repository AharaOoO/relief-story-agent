const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('reliefDesktop', {
  platform: process.platform,
  shell: 'electron',
  backend: {
    restart: () => ipcRenderer.invoke('relief:desktop:restart-backend'),
    status: () => ipcRenderer.invoke('relief:desktop:get-state'),
  },
  logs: {
    open: () => ipcRenderer.invoke('relief:desktop:open-logs'),
  },
  settings: {
    load: () => ipcRenderer.invoke('relief:desktop:get-state'),
    reset: () => ipcRenderer.invoke('relief:desktop:reset-settings'),
    save: (settings) =>
      ipcRenderer.invoke('relief:desktop:save-settings', settings),
  },
})
