# Relief Story Agent Desktop Shell

This is the future fan-facing desktop package skeleton. It is separate from the
immediate PowerShell desktop shortcut under `tools/desktop`.

## Development

Install Electron dependencies:

```powershell
npm --prefix desktop/electron install
```

Start the Vite UI in another terminal:

```powershell
cd frontend
npm run dev
```

Then launch the desktop shell:

```powershell
npm --prefix desktop/electron run dev
```

In development, Electron starts the Python API from the repository root and
loads `http://127.0.0.1:5173/` inside a desktop window.

## Future Fan Installer Pipeline

1. Build the React frontend:

   ```powershell
   npm --prefix frontend run build
   ```

2. Build the Python backend sidecar with PyInstaller:

   ```powershell
   python -m pip install pyinstaller
   pyinstaller --name relief-story-agent-api --onefile relief_story_agent/server.py
   ```

3. Copy the backend executable to:

   ```text
   desktop/electron/sidecar/bin/relief-story-agent-api.exe
   ```

4. Make sure the icon exists:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/Install-Shortcut.ps1 -DryRun
   powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/Install-Shortcut.ps1
   ```

5. Build the Windows installer:

   ```powershell
   npm --prefix desktop/electron run dist
   ```

The output installer will be under:

```text
desktop/electron/release/
```

## Notes

- Packaged mode expects `frontend/dist` to exist.
- Packaged mode expects `desktop/electron/sidecar/bin/relief-story-agent-api.exe`
  to exist.
- The app stores packaged runtime state under Electron `userData`.
