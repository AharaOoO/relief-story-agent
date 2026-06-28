# Relief Story Agent Desktop Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows desktop shortcut launcher now and lay down an Electron desktop packaging skeleton for a future one-click fan installer.

**Architecture:** The immediate launcher lives in `tools/desktop` and starts the Python API plus Vite UI, then opens the local UI. The packaging skeleton lives in `desktop/electron`, where Electron will later launch a packaged Python sidecar and load the built React UI inside a native desktop window.

**Tech Stack:** PowerShell, Windows `.lnk` COM shortcut creation, generated `.ico` assets, Electron 42, electron-builder 26, existing Vite/React frontend, existing Python FastAPI backend.

---

### Task 1: Launcher Smoke Test

**Files:**
- Create: `tools/desktop/tests/launcher-smoke.ps1`

- [x] **Step 1: Write the failing smoke test**

```powershell
$launcher = Join-Path $Root "tools\desktop\Start-ReliefStoryAgent.ps1"
$installer = Join-Path $Root "tools\desktop\Install-Shortcut.ps1"
$electronPackage = Join-Path $Root "desktop\electron\package.json"
foreach ($path in @($launcher, $installer, $electronPackage)) {
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Missing expected desktop file: $path"
  }
}
```

- [x] **Step 2: Run test to verify it fails**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/tests/launcher-smoke.ps1`

Expected: fails because `Start-ReliefStoryAgent.ps1` does not exist yet.

### Task 2: Windows Desktop Shortcut Launcher

**Files:**
- Create: `tools/desktop/Start-ReliefStoryAgent.ps1`
- Create: `tools/desktop/Install-Shortcut.ps1`
- Create: `tools/desktop/README.md`

- [x] **Step 1: Implement launcher dry-run contract**

`Start-ReliefStoryAgent.ps1 -DryRun` must output JSON with `backendPort=8891`, `frontendPort=5173`, and `frontendUrl=http://127.0.0.1:5173/`.

- [x] **Step 2: Implement launcher runtime**

The launcher must create `relief_story_state/launcher-logs`, start the backend if port `8891` is not listening, start the frontend if port `5173` is not listening, wait for `/api/health` and the frontend URL, then open the browser unless `-NoBrowser` is passed.

- [x] **Step 3: Implement shortcut installer**

`Install-Shortcut.ps1` must generate `tools/desktop/assets/relief-story-agent.ico`, create `Relief Story Agent.lnk` on the current user's Desktop, point it at the launcher, and expose a `-DryRun` JSON contract.

### Task 3: Electron Desktop Skeleton

**Files:**
- Create: `desktop/electron/package.json`
- Create: `desktop/electron/src/main.js`
- Create: `desktop/electron/src/preload.js`
- Create: `desktop/electron/README.md`

- [x] **Step 1: Create Electron package metadata**

Use package scripts `dev`, `pack`, and `dist`, with `electron` and `electron-builder` dev dependencies.

- [x] **Step 2: Create main process sidecar launcher**

In development, Electron starts `python -m relief_story_agent.server` from the repo root and loads `http://127.0.0.1:5173/`. In packaged mode, it looks for `resources/bin/relief-story-agent-api.exe` and loads packaged frontend assets.

- [x] **Step 3: Document packaging pipeline**

The README must describe the future sequence: build frontend, build PyInstaller backend exe, copy frontend and backend sidecar into Electron resources, then run electron-builder for a Windows installer.

### Task 4: Verification

**Files:**
- Verify all files above.

- [x] **Step 1: Run smoke test**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/tests/launcher-smoke.ps1`

Expected: prints `Desktop launcher smoke checks passed.`

- [x] **Step 2: Install desktop shortcut**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/Install-Shortcut.ps1`

Expected: creates a Desktop shortcut and generated icon.

- [x] **Step 3: Run syntax and metadata checks**

Run: `npm --prefix desktop/electron run check`

Expected: Electron metadata imports successfully.
