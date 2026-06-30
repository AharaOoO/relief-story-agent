# Ice Coast Workbench UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用全新冰海玻璃工作台替代旧管理台路径，并把创建、十步运行、队列、资产和高级设置全部连接真实后端。

**Architecture:** 新建 `app/workbench` 与按业务边界拆分的 feature 模块；React Query 管理服务器状态，Zustand 只保存 UI/草稿。首页、运行态和高级设置共享设计 token，不导入旧页面组件或 fixtures。

**Tech Stack:** React 19, TypeScript, React Router, TanStack Query, Zustand, Framer Motion, GSAP, Lucide, Vitest, Testing Library, Playwright/agent-browser

---

### Task 1: 修复测试基线并建立设计 token

**Files:**
- Modify: `frontend/src/test/setup.ts`
- Modify: `frontend/src/style-system.test.ts`
- Create: `frontend/src/app/workbench/workbench.css`
- Create: `frontend/src/app/workbench/tokens.ts`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: 给 jsdom 增加 `matchMedia` 测试 polyfill**，先运行现有 router 测试确认 GSAP 错误消失。
- [ ] **Step 2: 把样式测试改为设计规格中的冰白、玻璃、墨色、冰蓝 token**，先验证旧 CSS 失败。
- [ ] **Step 3: 实现 token、字体回退、focus、reduced-motion 和滚动条**，禁止 viewport 字号和负字距。
- [ ] **Step 4: 运行** `npm test -- --run src/style-system.test.ts src/app/router.test.tsx`，预期通过。
- [ ] **Step 5: 提交** `feat(ui): establish ice coast design system`。

### Task 2: 生成并接入离线背景资产

**Files:**
- Create: `frontend/src/assets/ice-coast-wave.webp`
- Create: `frontend/src/assets/ice-coast-caustics.webp`
- Create: `frontend/src/assets/ice-coast-horizon.webp`
- Modify: `frontend/src/shared/components/OceanVideoBackground.tsx`
- Test: `frontend/src/shared/components/OceanVideoBackground.test.tsx`

- [ ] **Step 1: 使用 image generation 生成三张 2K、无文字、上下边缘干净的连续冰海背景图**，输出 WebP。
- [ ] **Step 2: 写组件测试**，断言视频有 poster、背景图本地导入、底部 mask 和 reduced-motion 静态替代。
- [ ] **Step 3: 实现视频到 `#F7F9FC` 的 mask 过渡和三段背景层**。
- [ ] **Step 4: 运行组件测试并提交** `feat(ui): add offline ice coast ambience`。

### Task 3: 新工作台壳和路由隔离

**Files:**
- Create: `frontend/src/app/workbench/WorkbenchShell.tsx`
- Create: `frontend/src/app/workbench/WorkbenchNav.tsx`
- Create: `frontend/src/app/workbench/WorkbenchStatus.tsx`
- Modify: `frontend/src/app/router.tsx`
- Test: `frontend/src/app/router.test.tsx`

- [ ] **Step 1: 写失败路由测试**，要求 `/`, `/autopilot`, `/tasks`, `/assets`, `/run/:runId` 使用新壳，页面树不包含 `AppShell` 旧文案。
- [ ] **Step 2: 实现悬浮玻璃导航和响应式移动导航**，导航项为控制台/自动执行/任务队列/资产库/高级设置。
- [ ] **Step 3: 删除产品路由对旧 `AppShell` 的引用**，旧模块暂留源码但不进入 runtime bundle 路径。
- [ ] **Step 4: 运行 router 测试并提交** `feat(ui): replace legacy shell with workbench`。

### Task 4: 创建草稿与请求构建器

**Files:**
- Create: `frontend/src/features/run-composer/runDraft.store.ts`
- Create: `frontend/src/features/run-composer/runRequest.builder.ts`
- Create: `frontend/src/features/run-composer/runRequest.builder.test.ts`
- Modify: `frontend/src/modules/run-creation/contracts/run.contract.ts`

- [ ] **Step 1: 写失败测试**，覆盖 auto 空白、idea/requirements/script/mixed、16:9/9:16、2K、六阶段配置、Prompt Profile、ComfyUI 和 batch defaults。
- [ ] **Step 2: 实现类型化 draft 和 builder**，不使用 `any`；预检和创建共用同一 builder。
- [ ] **Step 3: 持久化非敏感草稿到 session storage**，预检 mutation 不清空 store。
- [ ] **Step 4: 运行测试并提交** `feat(ui): build complete autopilot run payloads`。

### Task 5: 首页任务发起台

**Files:**
- Create: `frontend/src/features/run-composer/RunComposer.tsx`
- Create: `frontend/src/features/run-composer/InputModeControl.tsx`
- Create: `frontend/src/features/run-composer/QuickOptions.tsx`
- Create: `frontend/src/features/run-composer/RunComposer.test.tsx`
- Modify: `frontend/src/pages/LandingPage.tsx`

- [ ] **Step 1: 写失败交互测试**，覆盖空白开始、输入识别、手动模式、导入剧本、预检保留草稿、pending/success/error。
- [ ] **Step 2: 重做首页**，海滩视频为首屏信号，核心输入不是卡片套卡片，下一段内容在首屏底部可见。
- [ ] **Step 3: 连接 `/api/config/validate` 与 `/api/runs`**，创建后导航 `/run/:runId`。
- [ ] **Step 4: 增加 1-20 任务数量并在大于 1 时调用 batch 创建**。
- [ ] **Step 5: 运行测试并提交** `feat(ui): add one-click and batch run composer`。

### Task 6: 十道工序真实工作台

**Files:**
- Create: `frontend/src/features/autopilot/stages.ts`
- Create: `frontend/src/features/autopilot/StageRail.tsx`
- Create: `frontend/src/features/autopilot/StageWorkspace.tsx`
- Create: `frontend/src/features/autopilot/RunOutputDock.tsx`
- Create: `frontend/src/features/autopilot/AutopilotPage.tsx`
- Create: `frontend/src/features/autopilot/AutopilotPage.test.tsx`

- [ ] **Step 1: 写失败测试**，把后端 stage/status 映射为十个固定工序，覆盖 pending/running/completed/failed/skipped/cancelled。
- [ ] **Step 2: 实现真实 run detail/timeline/events 轮询和 cursor 恢复**，页面刷新后继续当前 run。
- [ ] **Step 3: 实现当前阶段详情和右侧输出 dock**，错误展示 action，产物展示真实 URL/path。
- [ ] **Step 4: 连接 approve/retry/cancel 和 ComfyUI refresh**，每个按钮显示执行反馈。
- [ ] **Step 5: 运行测试并提交** `feat(ui): connect ten-stage autopilot workspace`。

### Task 7: 六阶段模型与提示词编辑

**Files:**
- Create: `frontend/src/features/prompt-profiles/promptProfiles.api.ts`
- Create: `frontend/src/features/prompt-profiles/StagePromptEditor.tsx`
- Create: `frontend/src/features/model-settings/providerCatalog.ts`
- Create: `frontend/src/features/model-settings/StageModelSelector.tsx`
- Test: `frontend/src/features/model-settings/providerCatalog.test.ts`
- Test: `frontend/src/features/prompt-profiles/StagePromptEditor.test.tsx`

- [ ] **Step 1: 写失败测试**，国内/国际模型不串台，普通 compatible 不显示 RH 列表，第 1-6 步都有 prompt 编辑器。
- [ ] **Step 2: 实现 catalog 与六阶段 selector**，数据与后端 catalog 契约一致。
- [ ] **Step 3: 连接 Prompt Profile CRUD**，支持保存、恢复默认、版本更新和未保存提醒。
- [ ] **Step 4: 在自动执行页面展开当前 1-6 步时复用 selector/editor**。
- [ ] **Step 5: 运行测试并提交** `feat(ui): configure six-stage models and prompts`。

### Task 8: 高级设置抽屉

**Files:**
- Create: `frontend/src/features/settings/AdvancedSettingsDrawer.tsx`
- Create: `frontend/src/features/settings/SecretSettings.tsx`
- Create: `frontend/src/features/settings/ComfySettings.tsx`
- Create: `frontend/src/features/settings/ExecutionSettings.tsx`
- Create: `frontend/src/features/settings/AdvancedSettingsDrawer.test.tsx`

- [ ] **Step 1: 写失败测试**，覆盖焦点圈定、Esc、六标签、masked key、保存反馈、工作流选择/拖拽和重启后读取。
- [ ] **Step 2: 实现抽屉与桌面 IPC adapter**；浏览器预览模式明确提示仅供界面预览，不伪装已保存。
- [ ] **Step 3: 工作流拖拽只接受单个 JSON，保存后调用后端 analyze/connect 并显示结果**。
- [ ] **Step 4: 密钥输入始终为空；已保存状态使用掩码摘要，修改时才发送新值**。
- [ ] **Step 5: 运行测试并提交** `feat(ui): add functional advanced settings drawer`。

### Task 9: 队列、资产与运行反馈统一

**Files:**
- Create: `frontend/src/features/tasks/TaskQueuePage.tsx`
- Create: `frontend/src/features/assets/AssetLibraryPage.tsx`
- Create: `frontend/src/shared/components/AsyncActionButton.tsx`
- Test: `frontend/src/features/tasks/TaskQueuePage.test.tsx`
- Test: `frontend/src/shared/components/AsyncActionButton.test.tsx`

- [ ] **Step 1: 写失败测试**，覆盖真实 batches/runs、pause/resume/cancel/retry、资产索引和按钮反馈。
- [ ] **Step 2: 实现任务队列和资产库**，不得导入 sample fixtures。
- [ ] **Step 3: 统一所有异步按钮的 loading 文案、spinner、禁用和 aria-live**。
- [ ] **Step 4: 运行测试并提交** `feat(ui): connect task queue and asset library`。

### Task 10: 响应式视觉回归与构建

**Files:**
- Modify: `frontend/src/app/workbench/workbench.css`
- Modify: `frontend/src/index.css`
- Test: `frontend/src/**/*.test.tsx`

- [ ] **Step 1: 运行** `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`，修复到全部通过。
- [ ] **Step 2: 启动本地开发服务**，用 Playwright/agent-browser 检查 1280x800、1440x900、1920x1080、440x900。
- [ ] **Step 3: 检查海滩可见、视频渐隐、文字不重叠、十步固定尺寸、抽屉不溢出、200% 缩放和 reduced-motion**。
- [ ] **Step 4: 检查浏览器控制台无 error，所有 API 请求指向 desktop handshake 后端 URL**。
- [ ] **Step 5: 提交** `test(ui): verify ice coast workbench end to end`。

