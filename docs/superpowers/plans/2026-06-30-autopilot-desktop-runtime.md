# Autopilot Desktop Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Windows 客户端可靠管理 sidecar、文件选择、非敏感配置和不回传明文的安全密钥。

**Architecture:** Electron 主进程是桌面权限边界；renderer 只能调用窄 IPC。密钥由 `safeStorage` 加密并只以环境变量注入新 sidecar，非敏感配置原子写入 AppData；保存后受控重启并重新握手。

**Tech Stack:** Electron, Node.js CommonJS, Vitest/Node test runner, Python sidecar

---

### Task 1: 提取可测试的设置存储

**Files:**
- Create: `desktop/electron/src/settings-store.js`
- Create: `desktop/electron/test/settings-store.test.js`
- Modify: `desktop/electron/src/main.js`

- [ ] **Step 1: 写失败测试**，覆盖原子写入、非敏感字段合并、密钥加密、密钥状态掩码和删除。
- [ ] **Step 2: 运行** `node --test desktop/electron/test/settings-store.test.js`，预期模块缺失。
- [ ] **Step 3: 实现 `SettingsStore`**，磁盘只保存 cipher；`getPublicSettings()` 只返回 `configured/masked`，`getEnvironment()` 仅供主进程启动 sidecar。
- [ ] **Step 4: 修改 `main.js` 使用 store**，删除向 renderer 返回解密值的旧 `get-settings` 行为。
- [ ] **Step 5: 运行测试并提交** `feat(desktop): secure runtime settings boundary`。

### Task 2: 窄 IPC 与文件选择

**Files:**
- Modify: `desktop/electron/src/main.js`
- Modify: `desktop/electron/src/preload.js`
- Modify: `frontend/src/vite-env.d.ts`
- Create: `desktop/electron/test/ipc-contract.test.js`

- [ ] **Step 1: 写失败测试**，断言 preload 只暴露 `getRuntimeConfig/saveRuntimeConfig/getSecretStatus/saveSecret/deleteSecret/pickWorkflow/pickScript/pickDirectory/openPath/restartBackend/getHandshake`。
- [ ] **Step 2: 实现文件和目录 dialog**，工作流限制 `.json`，剧本允许 `.txt/.md/.json`；返回取消状态而不是空异常。
- [ ] **Step 3: 实现密钥 IPC allowlist**：`RUNNINGHUB_CN_API_KEY`, `RUNNINGHUB_AI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `IMAGE_API_KEY`。
- [ ] **Step 4: 运行测试和 `node --check`**，预期通过。
- [ ] **Step 5: 提交** `feat(desktop): add safe file and secret ipc`。

### Task 3: Sidecar 日志、动态端口和受控重启

**Files:**
- Create: `desktop/electron/src/sidecar-manager.js`
- Create: `desktop/electron/test/sidecar-manager.test.js`
- Modify: `desktop/electron/src/main.js`

- [ ] **Step 1: 写失败测试**，覆盖端口占用时分配新端口、启动超时、进程退出、重启、退出清理和日志文件追加。
- [ ] **Step 2: 实现 `SidecarManager`**，开发与打包共享状态机；stdio 写入 AppData logs，并保留最近错误摘要。
- [ ] **Step 3: handshake 返回实际 backend URL、状态、版本和 last error**，前端不再假设 8891。
- [ ] **Step 4: 保存影响后端的设置后调用 `restart()`**，成功健康检查后才回报已生效。
- [ ] **Step 5: 运行测试并提交** `feat(desktop): supervise python sidecar lifecycle`。

### Task 4: 桌面运行时回归

**Files:**
- Modify: `desktop/electron/package.json`
- Test: `desktop/electron/test/*.test.js`

- [ ] **Step 1: 增加 `test` 和 `check` scripts**，不引入生产依赖。
- [ ] **Step 2: 运行** `npm test` 与 `npm run check`（工作目录 `desktop/electron`），预期通过。
- [ ] **Step 3: 启动开发客户端**，验证保存密钥后 renderer DOM 与 DevTools 中均看不到明文，重启后状态仍为已配置。
- [ ] **Step 4: 验证选择/拖拽工作流后重启客户端仍保留路径，并能通过后端分析**。
- [ ] **Step 5: 提交** `test(desktop): cover runtime configuration loop`。

