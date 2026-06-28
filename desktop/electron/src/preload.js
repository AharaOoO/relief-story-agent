const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('reliefDesktop', {
  platform: process.platform,
  shell: 'electron',
})
