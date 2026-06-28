# Desktop Client Settings Loop Design

## Problem

The project currently has an Electron shell and a local web console, but it still behaves like a developer launcher. Ports and local endpoints are visible, yet the user cannot edit them in a durable desktop-client flow. This makes the port display useful for debugging but weak for a normal desktop user.

## Goal

Build a desktop-client configuration loop:

- The Electron app is the primary entry point.
- Desktop settings are editable from the UI.
- Settings persist in the desktop user data directory.
- Backend startup reads those persisted settings.
- Changing backend settings gives the user an explicit save-and-restart action.
- The UI feels like a practical desktop control panel, not a static status page.

## Scope

This work adds the first durable desktop settings layer. It does not build a final Windows installer, bundle the Python sidecar executable, or remove the development web launcher. Those remain later packaging tasks.

## Architecture

Electron owns trusted local machine actions. The renderer never receives Node access; it uses a small preload bridge exposed as `window.reliefDesktop`.

The settings file lives under Electron `app.getPath("userData")` as `settings.json`. The main process loads defaults, merges saved values, validates incoming renderer updates, writes settings atomically, and restarts the backend process when requested.

The frontend detects whether it is running inside Electron. In Electron, it shows editable desktop settings with save, restart, logs, and reset actions. In browser-only development, it shows the same form with a clear "desktop bridge unavailable" state so the page stays understandable.

## Settings

Initial editable settings:

- `host`: default `127.0.0.1`
- `backendPort`: default `8891`
- `frontendPort`: default `5173`
- `comfyUiEndpoint`: default `http://127.0.0.1:8188`
- `workflowPath`: default `D:/ComfyUI/workflows/ltx23_four_grid.json`
- `stateDir`: default Electron user data `state`
- `logDir`: default Electron user data `logs`

Validation rules:

- Ports must be integers from `1024` to `65535`.
- Host must be non-empty.
- URLs must parse as `http:` or `https:`.
- Directory/path fields must be non-empty strings.

## User Experience

The Local Setup page becomes a desktop control panel:

- A top "Desktop Client" card shows shell status, backend URL, config file path, and whether settings need restart.
- Editable fields use clear labels and helper text.
- Primary action: "保存并重启本地服务".
- Secondary actions: "仅保存", "打开日志目录", "重置为默认值", "刷新状态".
- Backend connection and readiness remain visible beside settings.

The UI should avoid making the user think about ports unless they need to. Defaults should be usable; port fields are advanced-but-visible controls.

## Error Handling

- If the Electron bridge is missing, settings controls are disabled with a concise explanation.
- If saving fails, show the error near the settings card.
- If restart fails, keep the saved settings visible and show the failure.
- If the backend is unreachable after restart, the existing readiness/health cards show the blocked state.

## Testing

Electron:

- Unit-level Node tests cover default settings merge, validation, save/load, and backend argument construction.
- Existing `npm --prefix desktop/electron run check` remains.

Frontend:

- Component tests cover rendering saved settings, editing ports/endpoints, save-and-restart action, and bridge-missing state.
- Existing frontend typecheck, tests, and build must pass.

Launcher:

- Existing PowerShell smoke test remains.
- Dry-run JSON should include configurable host/ports so future installer scripts can reuse the same vocabulary.

