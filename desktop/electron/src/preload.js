const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('reliefDesktop', {
  platform: process.platform,
  shell: 'electron',
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),
  getHandshake: () => ipcRenderer.invoke('get-handshake'),
})
