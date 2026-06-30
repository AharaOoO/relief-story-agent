# Relief Story Agent Desktop Client

This Electron client supervises the local Python API, loads the offline React
workbench, and stores API keys with Windows secure storage.

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

## Windows Installer

Run the complete build from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/Build-Desktop.ps1
```

The script builds the offline frontend, creates the Python API sidecar, and
produces the NSIS installer under `desktop/electron/release/`.
The build machine needs the Windows Python launcher with Python 3.12 available
as `py -3.12`; the script creates its own isolated build environment.

To build only the frontend and sidecar while iterating:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/Build-Desktop.ps1 -SkipInstaller
```

## Manual Pipeline

1. Build the React frontend:

   ```powershell
   npm --prefix frontend run build
   ```

2. Build the Python backend sidecar with PyInstaller:

   ```powershell
   py -3.12 -m pip install pyinstaller
   py -3.12 -m PyInstaller --name relief-story-agent-api --onefile desktop/electron/sidecar/entry.py
   ```

3. Copy the backend executable to:

   ```text
   desktop/electron/sidecar/bin/relief-story-agent-api.exe
   ```

4. Keep the tracked application icon at
   `tools/desktop/assets/relief-story-agent.ico`.

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
