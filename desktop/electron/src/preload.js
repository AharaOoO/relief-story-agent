const { contextBridge, ipcRenderer } = require('electron')
const { createDesktopBridge } = require('./ipc-contract')

contextBridge.exposeInMainWorld(
  'reliefDesktop',
  createDesktopBridge(ipcRenderer.invoke.bind(ipcRenderer), process.platform),
)
