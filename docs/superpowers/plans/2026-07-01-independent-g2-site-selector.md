# Independent G2 Site Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give stage 8 an explicit domestic/international G2 selector that is independent from the six LLM stages and is faithfully persisted in every run request.

**Architecture:** Add `gridImageSite` to the persisted run draft while retaining `runninghubSite` as the default site for RunningHub LLM stage configuration. Migrate existing v4 drafts from their previous `runninghubSite`, bind all G2 controls and request serialization to the new field, and render the frozen G2 configuration for existing runs.

**Tech Stack:** React 19, TypeScript, Zustand, Vitest, Testing Library, Electron

---

### Task 1: Separate and migrate the G2 site draft field

**Files:**
- Modify: `frontend/src/features/run-composer/runRequest.builder.ts`
- Modify: `frontend/src/features/run-composer/runDraft.store.ts`
- Test: `frontend/src/features/run-composer/runRequest.builder.test.ts`
- Test: `frontend/src/features/run-composer/runDraft.store.migration.test.ts`

- [ ] **Step 1: Write failing tests**

Assert that `gridImageSite: 'cn'` serializes to `comfyui.grid_image.runninghub_site: 'cn'` without changing the LLM stage site, and that a v4 draft migrates its old `runninghubSite` value into `gridImageSite`.

- [ ] **Step 2: Run tests and confirm failure**

Run: `npm test -- --run src/features/run-composer/runRequest.builder.test.ts src/features/run-composer/runDraft.store.migration.test.ts`

- [ ] **Step 3: Implement the field and migration**

Add `gridImageSite` to `RunDraft`, use it in `buildRunRequest`, bump storage to v5, and derive a missing value from the stored `runninghubSite`.

- [ ] **Step 4: Run tests and confirm pass**

Run the same focused Vitest command and expect all tests to pass.

### Task 2: Make stage 8 directly configurable

**Files:**
- Modify: `frontend/src/features/autopilot/StageWorkspace.tsx`
- Modify: `frontend/src/index.css`
- Test: `frontend/src/features/autopilot/StageWorkspace.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Assert that stage 8 shows domestic and international G2 choices, changing the selection updates `gridImageSite`, and read-only mode displays the site frozen in the run request.

- [ ] **Step 2: Run the stage workspace test and confirm failure**

Run: `npm test -- --run src/features/autopilot/StageWorkspace.test.tsx`

- [ ] **Step 3: Implement the stage 8 panel**

Render a dedicated G2 configuration panel with site, model, aspect ratio, resolution, and the corresponding secret name. Disable controls in read-only mode and source values from `runRequest.comfyui.grid_image`.

- [ ] **Step 4: Run the stage workspace test and confirm pass**

Run the same focused Vitest command and expect all tests to pass.

### Task 3: Align every G2 entry point

**Files:**
- Modify: `frontend/src/features/run-composer/RunComposer.tsx`
- Modify: `frontend/src/features/settings/AdvancedSettingsDrawer.tsx`

- [ ] **Step 1: Replace G2 bindings**

Bind the quick composer and advanced image settings to `gridImageSite`, update labels to explicitly say G2 image site, and leave per-stage LLM site selectors untouched.

- [ ] **Step 2: Verify type safety and lint**

Run: `npm run typecheck && npm run lint`

### Task 4: Verify and package the desktop client

**Files:**
- Build output: `frontend/dist`
- Build output: `desktop/electron/release/win-unpacked`

- [ ] **Step 1: Run frontend verification**

Run: `npm test && npm run build`

- [ ] **Step 2: Run Electron verification**

Run: `npm test && npm run check && npm run pack`

- [ ] **Step 3: Deploy the unpacked client**

Replace the existing desktop test copy only after the packaged application has been closed, preserving the user's AppData configuration and encrypted secrets.

- [ ] **Step 4: Launch and smoke-test**

Confirm the sidecar is online, stage 8 exposes the selector, and a generated request carries the selected site without exposing any secret value.
