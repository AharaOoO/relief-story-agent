# Desktop Client Settings Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real desktop-client settings loop where users can edit local ports/endpoints, persist them, and restart the backend from the Electron UI.

**Architecture:** Move desktop-specific configuration into focused Electron modules, expose safe IPC methods through preload, and consume them from a new Local Setup settings panel. The frontend remains browser-compatible by gracefully detecting when the Electron bridge is unavailable.

**Tech Stack:** Electron main/preload, Node `node:test`, React, HeroUI, TanStack Query, Zustand, Vitest, PowerShell launcher smoke tests.

---

## Files

- Create: `desktop/electron/src/settings.js` for default settings, validation, load/save, and config paths.
- Create: `desktop/electron/src/backend.js` for backend URL and spawn argument construction.
- Create: `desktop/electron/src/settings.test.js` for Node tests.
- Modify: `desktop/electron/src/main.js` to use settings and handle IPC.
- Modify: `desktop/electron/src/preload.js` to expose `settings.load`, `settings.save`, `backend.restart`, `backend.status`, `logs.open`.
- Modify: `desktop/electron/package.json` to add a `test` script.
- Create: `frontend/src/shared/contracts/desktop.contract.ts` for bridge and settings types.
- Create: `frontend/src/shared/desktop/desktopBridge.ts` for safe bridge access.
- Create: `frontend/src/modules/local-setup/components/DesktopSettingsPanel.tsx`.
- Create: `frontend/src/modules/local-setup/components/DesktopSettingsPanel.test.tsx`.
- Modify: `frontend/src/modules/local-setup/pages/LocalSetupPage.tsx` to surface the new panel.
- Modify: `frontend/src/modules/local-setup/components/BackendStatusCard.tsx` so the API URL can reflect desktop settings after save.
- Modify: `frontend/src/shared/store/uiStore.ts` to add persistent API/ComfyUI setters used by desktop settings.
- Modify: `frontend/src/index.css` to polish the Local Setup layout and form ergonomics.
- Modify: `tools/desktop/Start-ReliefStoryAgent.ps1` and `tools/desktop/Start-ReliefStoryAgentDesktop.ps1` only if dry-run output or argument names need to stay aligned.

## Tasks

### Task 1: Electron Settings Module

- [ ] Write `desktop/electron/src/settings.test.js` using `node:test`.
- [ ] Verify it fails because `settings.js` does not exist.
- [ ] Implement `settings.js` with defaults, validation, atomic save/load, and path helpers.
- [ ] Run `npm --prefix desktop/electron run test`.
- [ ] Run `npm --prefix desktop/electron run check`.

### Task 2: Backend Process Builder

- [ ] Extend `settings.test.js` to assert backend URLs and spawn arguments come from settings.
- [ ] Verify the test fails because `backend.js` does not exist.
- [ ] Implement `backend.js`.
- [ ] Refactor `main.js` to use `settings.js` and `backend.js`.
- [ ] Run `npm --prefix desktop/electron run test` and `npm --prefix desktop/electron run check`.

### Task 3: Preload IPC Bridge

- [ ] Add tests or static checks that preload exposes `reliefDesktop.settings`, `reliefDesktop.backend`, and `reliefDesktop.logs`.
- [ ] Verify failure before implementation.
- [ ] Add IPC handlers in `main.js`.
- [ ] Add safe bridge methods in `preload.js`.
- [ ] Run Electron tests/checks.

### Task 4: Frontend Desktop Settings Panel

- [ ] Write `DesktopSettingsPanel.test.tsx` for bridge available, editing values, save-and-restart, and bridge missing.
- [ ] Verify the test fails because the component does not exist.
- [ ] Implement desktop contracts, bridge adapter, and `DesktopSettingsPanel`.
- [ ] Add the panel to `LocalSetupPage`.
- [ ] Run targeted Vitest test, then full frontend tests.

### Task 5: UI Polish

- [ ] Improve Local Setup copy, layout density, field helpers, alert states, and action hierarchy.
- [ ] Keep controls usable on desktop and mobile widths.
- [ ] Run typecheck, test, and build.

### Task 6: Final Verification and PR

- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File tools/desktop/tests/launcher-smoke.ps1`.
- [ ] Run `npm --prefix desktop/electron run test`.
- [ ] Run `npm --prefix desktop/electron run check`.
- [ ] Run `npm --prefix frontend run typecheck`.
- [ ] Run `npm --prefix frontend run test`.
- [ ] Run `npm --prefix frontend run build`.
- [ ] Commit with `feat: add desktop settings loop`.
- [ ] Push branch and create PR.

