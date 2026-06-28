# Relief Story Agent Desktop Launcher

This folder contains the Windows launcher for local development and operator use.

## Install the Desktop Shortcut

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/Install-Shortcut.ps1
```

This creates:

- Desktop shortcut: `Relief Story Agent.lnk`
- Icon: `tools/desktop/assets/relief-story-agent.ico`
- Icon preview: `tools/desktop/assets/relief-story-agent-icon-preview.png`

The icon uses the same cream, gold, chocolate, cobalt, and mint palette as the
React UI.

## Launch

Double-click `Relief Story Agent` on the desktop.

The launcher starts:

- Backend API: `http://127.0.0.1:8891`
- Frontend UI: `http://127.0.0.1:5173/`

Logs are written under:

```text
relief_story_state/launcher-logs/
```

## Dry Run

To inspect what the launcher would do without starting services:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/Start-ReliefStoryAgent.ps1 -DryRun
```

To inspect the shortcut target without creating it:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/Install-Shortcut.ps1 -DryRun
```

## Future Installer

This shortcut is the immediate local launcher. The future fan-facing installer
should use the Electron package skeleton under `desktop/electron`, with the
Python backend bundled as a sidecar executable.

## Install the Desktop App Shortcut

The browser shortcut is useful for development, but the standalone software
entry is the Electron desktop client:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/Install-DesktopShortcut.ps1
```

This creates:

```text
Desktop/Relief Story Agent Desktop.lnk
```

Double-click this shortcut to open the UI in its own desktop app window instead
of the default browser. The first launch may install Electron dependencies if
`desktop/electron/node_modules` is missing.
