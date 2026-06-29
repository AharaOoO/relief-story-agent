# Relief Story Agent 交给 Gemini 3.5 Flash 的完整开发交接文件

> 交接日期：2026-06-29
>
> 接手模型：Gemini 3.5 Flash
>
> GitHub：`https://github.com/AharaOoO/relief-story-agent`
>
> Windows 本地仓库：`D:\codex工作区`
>
> 产品规格：`docs/superpowers/specs/2026-06-29-relief-story-agent-beach-autopilot-development-spec-zh.md`
>
> 当前文档 PR：`https://github.com/AharaOoO/relief-story-agent/pull/4`

---

## 0. 给 Gemini 的直接执行指令

你正在接手一个已经有大量后端能力、但 Git 分支和 UI 实验状态比较复杂的 Windows 桌面项目。你的任务不是从零重写整个项目，也不是继续给旧 UI 换皮。请先保护现有工作，再按本文件和产品规格逐 Work Packet 开发。

开始前必须执行：

1. 阅读仓库根目录 `AGENTS.md`。
2. 阅读本交接文件全文。
3. 阅读海滩自动制片工作台产品规格全文。
4. 获取 GitHub 最新状态，不能假设本文记录的 PR 状态仍未变化。
5. 检查所有 worktree 和 dirty 状态。
6. 不得在 `D:\codex工作区` 当前脏工作树中直接做新的正式开发提交。
7. 不得执行 `git reset --hard`、`git checkout -- .`、`git clean -fd`、批量删除或覆盖现有改动。
8. 为第一个 Work Packet 创建独立 clean worktree 和独立分支。
9. 每个 Work Packet 只做一个可审查的目标，配套测试后单独提交和创建 PR。
10. 所有用户界面必须从新工作台架构重新实现，不继承旧 UI 的布局和视觉。

你的第一条回复必须用中文报告：

1. 当前 `origin/master` commit。
2. PR #3、PR #4 的最新状态。
3. 主工作区和其他 worktree 的分支、dirty 状态。
4. 你确认不会破坏的本地改动。
5. 你准备执行的第一个 Work Packet、文件范围、测试范围和退出条件。

如果用户回复“继续”或明确允许实施，从本文件第 17 节开始执行。

---

## 1. 项目一句话目标

Relief Story Agent 是一个 Windows 本地桌面 AI 短剧自动制片工具。用户可以留空一键创作，也可以输入灵感、创作要求或已有剧本；系统自动完成剧本、改稿、质量门禁、导演分镜、LTX 2.3 提示词、提示词审查与修正、G2 四宫格参考图、产物整理和本地 ComfyUI/LTX 2.3 队列提交。

目标产品形态是“一页式海滩自动制片工作台”：海滩背景在发起、运行和完成状态下都明显存在，核心操作是快速创建单条或批量任务，并观察真实十阶段流水线。

---

## 2. 需求优先级与事实源

发生冲突时按以下顺序决定：

1. 用户最新明确要求。
2. 本交接文件中标记为“已确认”的产品决定。
3. 海滩自动制片工作台产品规格。
4. GitHub `origin/master` 的真实代码行为。
5. 已合并 PR 的行为。
6. 未合并 PR、本地提交和未提交候选代码。
7. 历史交接文件和旧 UI 文案。

以下文件是历史材料，不得覆盖新规格：

1. `PROJECT_HANDOFF.md`
2. `NEXT_SESSION_HANDOFF_REPORT.md`
3. `NEXT_SESSION_PROMPT.md`
4. `PROJECT_STATUS.md`

这些文件可用于理解后端演进，但其中的完成度、下一步和 UI 方向已部分过期。

---

## 3. 已确认的产品决定

### 3.1 产品形态

1. 必须是 Desktop App，不是要求用户自己运行前端预览端口的网站。
2. 首页、运行态和完成态都使用同一个海滩工作壳。
3. 不得在新工作壳中嵌入整张旧页面。
4. 创建成功后不得跳转回旧 `AppShell`。
5. 常用操作留在首页，高级参数放入抽屉或对话框。

### 3.2 用户输入

必须支持：

1. 空白自动起题。
2. 一句灵感。
3. 一段创作要求。
4. 完整已有剧本。
5. 剧本 + 附加要求。
6. 多行批量任务。
7. 多文件剧本导入。

预检、切换比例、打开设置和创建失败均不得清空用户草稿。

### 3.3 图像要求

已确认，不再等待产品决策：

1. RunningHub G2 和 GPT Image 默认使用 2K。
2. 默认比例为 16:9。
3. 用户可以切换 9:16。
4. 四宫格校验必须服从用户所选比例，不能继续固定要求 1:1。
5. 国内站和国际站必须分别真实测试请求、轮询和结果下载。

### 3.4 模型调用模式

必须区分：

1. RunningHub 便捷 API 模式：同一站点使用一个 `RUNNINGHUB_API_KEY`，覆盖 LLM 与 G2。
2. 普通 OpenAI-compatible provider 模式：分别配置 Gemini、DeepSeek、OpenAI/兼容模型。
3. RunningHub 国内站 `.cn` 与国际站 `.ai` 的精选模型列表必须分开维护。
4. 模型供应商模式与视频渲染后端是两个独立概念。
5. 第一版正式视频渲染目标是本地 ComfyUI/LTX 2.3。
6. 独立 RunningHub 云工作流 API 不能冒充已经接入 Run Pipeline 的视频渲染模式。

### 3.5 十阶段与 LLM

第 1 至第 5 步必须调用 LLM。第 6 步只在第 5 步发现问题时调用 LLM；如果审查通过，必须显示“无需回锅/已跳过”，避免无意义费用。

---

## 4. GitHub 与本地代码的四层状态

以下是 2026-06-29 交接时的快照。接手时必须重新执行命令确认。

### 4.1 GitHub master

交接时：

```text
origin/master = 0d5cd22
```

已经合并：

1. PR #1：Windows desktop launcher。
2. PR #2：local readiness UI console。

GitHub master 是“已交付事实”的主要基线。

### 4.2 未合并 PR

交接时：

1. PR #3：`feat: add desktop settings loop`，OPEN，merge state CLEAN，但没有 CI checks。
2. PR #4：本文档和产品规格，OPEN，merge state CLEAN。

不要假设它们仍然 open。接手后执行：

```powershell
gh pr list --repo AharaOoO/relief-story-agent --state all --limit 20
gh pr view 3 --repo AharaOoO/relief-story-agent
gh pr view 4 --repo AharaOoO/relief-story-agent
```

### 4.3 主工作区

路径：

```text
D:\codex工作区
```

交接时分支：

```text
codex/wp-002-local-readiness-ui
```

这是一个脏工作树，包含大量已修改和未跟踪文件。它混合了：

1. RunningHub 便捷 LLM/G2 候选代码。
2. 2K、16:9、9:16 候选配置。
3. 六阶段补充提示词路径候选。
4. 新海滩 `ImmersiveWorkspacePage` 实验。
5. 旧页面改动。
6. 另一套 `desktop/electron/main.cjs`、`preload.cjs` 和打包产物。
7. 其他与本项目无关的工作区目录。

不得在这里 reset、clean、stash all 或批量提交。

### 4.4 WP-004 本地 worktree

交接时存在另一个 worktree：

```text
C:\Users\dcf\.config\superpowers\worktrees\relief-story-agent\codex-wp-003-desktop-settings
```

其分支是：

```text
codex/wp-004-ui-redesign-comfynexus-moblinks
```

该 worktree 也有大量未提交改动。其最新本地提交为：

```text
f6b783f fix: allow slower ComfyUI runtime checks
```

该分支交接时没有对应远端分支。不要把它当成 GitHub 已完成状态。

### 4.5 文档 worktree

本交接文件创建于 clean 文档 worktree：

```text
C:\Users\dcf\.config\superpowers\worktrees\relief-story-agent\beach-autopilot-spec
branch: codex/beach-autopilot-spec
```

它只用于产品规格与交接文档，不应在这里直接开发业务代码。

---

## 5. 绝对禁止的 Git 操作

除非用户逐项明确批准，不得：

1. 在任何 dirty worktree 执行 `git reset --hard`。
2. 执行 `git clean -fd` 或清理所有未跟踪文件。
3. 执行 `git checkout -- .`。
4. 执行会覆盖用户改动的批量复制。
5. 把整个当前工作区一次提交。
6. 把构建产物、node_modules、密钥、`.env`、用户剧本或机器本地路径提交到 Git。
7. 因为新 UI 不采用旧视觉，就删除脏工作树里的旧文件。
8. 未验证就将本地 WP-004 或 RunningHub 候选直接推到 master。

安全做法：从最新 `origin/master` 创建独立 worktree，在新分支中重新实现或有选择地移植小块候选代码。

---

## 6. 建议的接手环境流程

### 6.1 只读审计

在主仓库执行：

```powershell
Set-Location 'D:\codex工作区'
git fetch --prune origin
git status --short --branch
git worktree list --porcelain
git branch -vv
gh pr list --repo AharaOoO/relief-story-agent --state all --limit 20
```

### 6.2 确定基线

优先建议：

1. 审查并合并 PR #3，或明确不采用。
2. 合并 PR #4，让规格和交接进入 master。
3. 再从更新后的 `origin/master` 创建第一个实施 worktree。

如果用户暂时不合并 PR，Gemini 仍可以读取 PR #4 分支上的规格，但正式开发分支应清楚记录 parent commit。

### 6.3 创建新 worktree

示例：

```powershell
git worktree add `
  'C:\Users\dcf\.config\superpowers\worktrees\relief-story-agent\gemini-wp-101' `
  -b gemini/wp-101-contract-baseline `
  origin/master
```

路径和分支若已存在，换一个明确名称；不要覆盖现有 worktree。

### 6.4 基线验证

在新 worktree 中：

```powershell
python -m pytest -q relief_story_agent/tests tests
Set-Location frontend
npm ci
npm test
npm run build
```

如果基线测试失败，先报告，不要把既有失败归因于本次修改。

---

## 7. 本地验证快照

2026-06-29 在主工作区完成：

| 命令 | 结果 |
|---|---|
| `python -m pytest -q relief_story_agent/tests tests` | 452 passed |
| `npm test`（frontend） | 18 test files、46 tests passed |
| `npm run build`（frontend） | TypeScript 与 Vite build 成功 |
| `node --check main.cjs` | 通过 |
| `node --check preload.cjs` | 通过 |

仓库根直接运行 `python -m pytest -q` 会收集同一大工作区中的其他独立项目，并因缺少 `redis`、`ltx23_merge`、`wc_player_agent` 等依赖中断。这不是 Relief Story Agent 失败。后续应增加 pytest 发现范围隔离，但不要把其他项目依赖安装进本项目来掩盖问题。

---

## 8. 当前后端真实完成度

### 8.1 GitHub master 已有

1. 十阶段规范顺序。
2. 单任务创建与持久化。
3. 批量任务创建、defaults 和 failure policy。
4. PersistentRunScheduler、优先级、worker、lease 和恢复。
5. 失败分类、重试、取消和审计。
6. Gemini 总编剧。
7. DeepSeek 改稿。
8. 本地确定性剧本质量门禁。
9. GPT 分镜提示词。
10. GPT 提示词审查。
11. 条件式 GPT 提示词修正。
12. 最终提示词阶段。
13. 四宫格提示词编译。
14. OpenAI-compatible 图片 provider。
15. ComfyUI 工作流分析和 LTX 自动注入。
16. ComfyUI prompt 提交、等待、取消、诊断和输出下载。
17. 产物、manifest、batch export 和 export validation。
18. run events、run timeline、batch timeline、metrics。
19. local doctor、readiness、acceptance status。
20. Electron 基础后端启动、健康等待和退出停止。

### 8.2 本地候选但未进入 GitHub master

1. `RunningHubLLMProvider`。
2. `RunningHubImageTaskProvider`。
3. provider router。
4. `provider` 字段和 RunningHub 模式 setup 配置。
5. 2K/16:9/9:16/1:1 image presets。
6. RunningHub image submit、query、download。
7. 六阶段补充模板路径。
8. RunningHub 国内/国际精选模型前端候选。
9. 桌面密钥保存候选。
10. 海滩沉浸页候选。

这些代码只能作为参考或逐块移植来源，不能作为已完成能力写入发布说明。

### 8.3 后端必须补齐

1. `RunRequest V2`：输入模式、创作参数、Prompt Profile、渲染后端。
2. 第 3 步 LLM 质量审查 + 本地硬规则。
3. 第 2/3 步最多一次受控回炉。
4. 第 5/6 步修正后再次审查。
5. FinalPromptPackage 快照。
6. Prompt Profile 正式存储、版本和运行快照。
7. 配置原子保存、版本、热应用和重启握手。
8. RunningHub 国内/国际真实能力验证。
9. 四宫格比例校验修复。
10. ComfyUI 全局分发背压和可见队列位置。
11. 可选 SSE 或可靠增量轮询。
12. 统一桌面入口和可复现 sidecar 构建。

---

## 9. 十阶段不可破坏顺序

| # | UI 烹饪标签 | 技术 stage ID | 当前/目标 |
|---:|---|---|---|
| 1 | 备料 | `chief_screenwriter` | LLM，总编剧和故事内核 |
| 2 | 慢炖 | `deepseek_polish` | LLM，改稿与受控回炉 |
| 3 | 试味 | `quality_gate` | 目标为 LLM 审查 + 本地硬门禁 |
| 4 | 配菜 | `gpt_prompt_writer` | LLM，导演分镜、LTX/G2 prompts |
| 5 | 调味 | `gpt_prompt_audit` | LLM，空间、轴线、动作和提示词审查 |
| 6 | 回锅 | `gpt_prompt_reviser` | 审查失败时 LLM 修正一次 |
| 7 | 锁菜谱 | `final_prompts` | 本地校验和快照冻结 |
| 8 | 出盘 | `four_grid_asset` | G2/GPT Image 四宫格生成与上传 |
| 9 | 打包 | `artifacts` | 产物、manifest、审计和可复现信息 |
| 10 | 出餐中 | `comfyui` | 本地 ComfyUI/LTX 2.3 排队和输出 |

不得改变宏观十阶段顺序。第 2/3 步和第 5/6 步可以在阶段内部按预算回环，但 UI 仍显示十个宏观阶段和轮次。

---

## 10. 后端关键文件地图

| 文件 | 作用 | 修改注意事项 |
|---|---|---|
| `relief_story_agent/pipeline.py` | 十阶段事实源 | 不随意改 stage ID；schema 与测试同步 |
| `relief_story_agent/models.py` | Pydantic 契约 | 新字段优先向后兼容；密钥 exclude |
| `relief_story_agent/orchestrator.py` | 十阶段执行与恢复 | 副作用必须幂等；控制循环预算 |
| `relief_story_agent/content.py` | 总编剧和改稿 prompt | 把疗愈短片硬编码迁移为 preset |
| `relief_story_agent/quality.py` | 本地硬规则 | 未来作为 LLM 门禁后的不可绕过规则 |
| `relief_story_agent/prompt_templates.py` | 分镜、审查、修正模板 | 迁移到 Prompt Profile 时保持默认模板 |
| `relief_story_agent/model_config.py` | 模型 profile resolve | 区分 provider 与 stage binding |
| `relief_story_agent/providers.py` | LLM provider | 本地 RunningHub 候选需独立移植和测试 |
| `relief_story_agent/image_providers.py` | 图片 provider | 国内/国际响应和错误必须真实测试 |
| `relief_story_agent/grid_image.py` | 四宫格 prompt 和图片校验 | 当前近似 1:1 校验必须改 |
| `relief_story_agent/comfyui.py` | 工作流注入和提交 | 保持 workflow 不由系统生成 |
| `relief_story_agent/ltx_workflow.py` | LiteGraph/LTX 分析 | 不破坏现有 60-node 工作流适配 |
| `relief_story_agent/scheduler.py` | 持久化调度 | pause/resume/recover 语义必须保持 |
| `relief_story_agent/resource_limits.py` | 并发限制 | ComfyUI 默认并发 1 |
| `relief_story_agent/config_validation.py` | preflight | 新 V2 字段和 Prompt Profile 必须纳入 |
| `relief_story_agent/api.py` | FastAPI endpoints | 使用稳定错误 code；保持旧 request 兼容 |
| `relief_story_agent/storage.py` | JSON 持久化 | 新字段需兼容旧状态文件 |
| `relief_story_agent/artifacts.py` | 产物写入 | 新快照和质量报告需加入 manifest |

---

## 11. 当前 API 资产

新 UI 优先复用这些真实 endpoint：

### 11.1 健康与配置

1. `GET /api/health`
2. `GET /api/local/bootstrap`
3. `GET /api/local/doctor`
4. `GET /api/local/readiness`
5. `GET /api/config/models`
6. `POST /api/config/model-check`
7. `GET /api/pipeline/schema`
8. `POST /api/config/validate`
9. `POST /api/config/diagnose`
10. `POST /api/config/validate-batch`
11. `POST /api/config/diagnose-batch`

### 11.2 Run

1. `POST /api/runs`
2. `GET /api/runs`
3. `GET /api/runs/{run_id}`
4. `GET /api/runs/{run_id}/events`
5. `GET /api/runs/{run_id}/audit`
6. `GET /api/runs/{run_id}/timeline`
7. `GET /api/runs/{run_id}/artifacts`
8. `POST /api/runs/{run_id}/approve`
9. `POST /api/runs/{run_id}/retry`
10. `POST /api/runs/{run_id}/cancel`
11. `POST /api/runs/{run_id}/refresh-comfyui`

### 11.3 Batch

1. `POST /api/batches/plan`
2. `POST /api/batches`
3. `GET /api/batches`
4. `GET /api/batches/{batch_id}`
5. `GET /api/batches/{batch_id}/timeline`
6. `GET /api/batches/{batch_id}/artifacts`
7. `GET /api/batches/{batch_id}/recovery-plan`
8. `GET /api/batches/{batch_id}/health`
9. `POST /api/batches/{batch_id}/pause`
10. `POST /api/batches/{batch_id}/resume`
11. `POST /api/batches/{batch_id}/retry`
12. `POST /api/batches/{batch_id}/cancel`
13. `POST /api/batches/{batch_id}/export`

### 11.4 ComfyUI

1. `POST /api/comfyui/connect`
2. `POST /api/comfyui/analyze-workflow`
3. `POST /api/comfyui/discover-workflows`
4. `POST /api/comfyui/preview`
5. `POST /api/comfyui/outputs`
6. `POST /api/smoke/comfyui`

### 11.5 RunningHub 云工作流

1. `POST /api/runninghub/check`
2. `POST /api/runninghub/submit`
3. `POST /api/runninghub/status`
4. `POST /api/runninghub/outputs`

这些 RunningHub endpoint 是独立 workflow API。不要误认为它们已经让 `RunRequest` 支持 RunningHub 便捷 LLM 或 G2。

---

## 12. 建议新增的 API

按产品规格实现：

1. `GET /api/settings/runtime`
2. `PUT /api/settings/runtime`
3. `POST /api/settings/runtime/validate`
4. `GET /api/prompt-profiles`
5. `POST /api/prompt-profiles`
6. `GET /api/prompt-profiles/{id}`
7. `PUT /api/prompt-profiles/{id}`
8. `POST /api/prompt-profiles/{id}/validate`
9. `POST /api/prompt-profiles/{id}/clone`
10. `POST /api/prompt-profiles/{id}/reset`
11. `GET /api/capabilities/models`
12. `POST /api/inputs/inspect`
13. 可选：`GET /api/runs/{id}/stream`
14. 可选：`GET /api/batches/{id}/stream`

新增 API 前先定义 Pydantic 和 TypeScript contract tests，不要先写页面再猜 payload。

---

## 13. RunningHub 候选代码移植规则

### 13.1 可参考的本地文件

主工作区中存在未提交候选差异：

1. `relief_story_agent/providers.py`
2. `relief_story_agent/image_providers.py`
3. `relief_story_agent/models.py`
4. `relief_story_agent/setup_wizard.py`
5. `relief_story_agent/server.py`
6. 对应 tests。

### 13.2 移植方式

1. 在 clean branch 上重新实现或逐小块 port。
2. 不使用“复制整个文件覆盖 master”。
3. 先新增 provider unit tests。
4. 再新增 router tests。
5. 再新增 setup/config validation tests。
6. 最后接入 UI。

### 13.3 必须验证

1. 国内 LLM base URL。
2. 国际 LLM base URL。
3. 国内 G2 submit endpoint。
4. 国际 G2 submit endpoint。
5. query endpoint 和字段。
6. 成功、失败、超时状态。
7. 返回图片 URL 和 content type。
8. 401、403、429 和业务 errorCode。
9. 16:9 2K。
10. 9:16 2K。

不要把截图中的模型名字当作永久 API 能力。使用官方 RunningHub 页面和真实请求确认，模型清单版本化，并保留站点字段。

---

## 14. Prompt Profile 目标

现有本地候选只是 `stage_prompt_template_paths`，这不够。

正式 Prompt Profile 至少包含：

```text
id
name
description
version
created_at
updated_at
source
content_hash
stages.chief_screenwriter
stages.deepseek_polish
stages.quality_gate
stages.gpt_prompt_writer
stages.gpt_prompt_audit
stages.gpt_prompt_reviser
```

规则：

1. 六阶段都有默认模板与用户补充区。
2. 基础系统契约不可被普通用户完全删除。
3. 支持 clone、reset、import、export、validate。
4. 每次 run 保存 profile ID、version、hash 和实际内容快照。
5. 修改全局 profile 不影响已经创建的 run。
6. 允许本次任务临时覆盖，但不自动改全局 profile。
7. 不在 profile 中保存 API key。

---

## 15. UI 必须全量重做

### 15.1 不允许继续使用的产品结构

1. 旧 `AppShell`。
2. 旧 Sidebar 和 Topbar。
3. 旧管理台多页面作为主产品入口。
4. `ImmersiveWorkspacePage` 把多个旧页面纵向拼接的方式。
5. 创建后跳到旧 review route。
6. 生产运行时 sample fixtures。
7. 巨型标题、Impact、异常字重和大量 `vw` 字号。
8. 卡片套卡片。
9. 远程海滩视频和音效 hotlink。

### 15.2 可以复用

1. API client。
2. TanStack Query 基础配置。
3. TypeScript contracts，经 V2 升级后继续用。
4. 错误规范化。
5. 日期、大小、状态格式化工具。
6. 经审查的无视觉基础组件。

### 15.3 新模块结构

```text
frontend/src/app/workbench/
frontend/src/features/task-launcher/
frontend/src/features/run-pipeline/
frontend/src/features/batch-tray/
frontend/src/features/result-dock/
frontend/src/features/settings/
frontend/src/shared/api/
frontend/src/shared/desktop/
```

### 15.4 三种主状态

1. 发起态：输入、任务数量、时长、比例、预设、一键开做、高级配置。
2. 运行态：同一海滩壳中的十阶段、当前任务、批次托盘、恢复动作。
3. 完成态：四宫格、视频、产物、导出、重做和阶段证据。

### 15.5 海滩要求

1. 海滩必须在工作状态仍明显可见。
2. 使用本地打包视频/poster。
3. 1280x800 中直接可见背景约不低于 30%。
4. 主工作面可以半透明，但不能完全盖住海景。
5. 低动态模式暂停视频。
6. 音频默认关闭。
7. 不能用装饰性渐变、光球或 bokeh 代替真实海滩素材。

### 15.6 字体与布局

1. 字体：Segoe UI Variable、Microsoft YaHei UI、Segoe UI、sans-serif。
2. 产品标题 36-40px。
3. 页面标题 28-32px。
4. 区域标题 20-24px。
5. 正文 14px。
6. 字重只用 400、500、600、700。
7. `letter-spacing: 0`。
8. 不按 viewport width 缩放正文。
9. 卡片圆角 6-8px。
10. 不允许卡片套卡片。

---

## 16. Electron 与桌面运行时

### 16.1 GitHub master 已有

`desktop/electron/src/main.js` 已能：

1. 启动开发环境 Python 后端。
2. 等待 `/api/health`。
3. 加载开发前端或 packaged frontend。
4. 退出时停止后端。

不要再声称 Electron 完全不会启动后端。

### 16.2 PR #3 候选

PR #3 添加：

1. desktop settings。
2. backend restart。
3. open logs。
4. settings IPC 和测试。

是否合并以最新 PR 状态和审查为准。

### 16.3 必须补齐

1. 动态 loopback 端口或可靠端口冲突处理。
2. stdout/stderr 日志文件，而不是 `stdio: ignore`。
3. sidecar crash supervision。
4. 版本握手。
5. 工作流文件选择。
6. 剧本文件选择。
7. 输出目录选择。
8. reveal artifact/open logs。
9. 安全密钥保存、状态和删除。
10. 可复现 sidecar build。
11. 安装包真实 smoke test。

### 16.4 两套 Electron 入口冲突

主工作区存在未提交 `main.cjs/preload.cjs`，GitHub 正式入口是 `src/main.js/src/preload.js`。正式开发以 GitHub `src/` 入口为基线，选择性移植 IPC；不要让两套入口长期共存。

---

## 17. 推荐实施顺序

不要一次实现 13 个 Work Packet。按以下波次执行。

### Wave 0：仓库与证据整理

目标：建立可开发的 clean baseline。

任务：

1. 重新确认 PR #3/#4。
2. 确认最新 master。
3. 创建 clean worktree。
4. 跑基线测试。
5. 写 `plans/active.md` 或独立 WP 实施计划。
6. 为本地候选代码建立只读差异清单。

退出条件：新 worktree clean、测试通过、分支 parent 明确、没有用户本地文件被改动。

### Wave 1：契约与配置基础

依次执行：

1. WP-101：RunRequest V2 与旧 UI 隔离。
2. WP-102：Prompt Profile 后端。
3. WP-107：桌面配置与安全密钥。
4. WP-108 的基础部分：统一桌面入口和运行时握手。

退出条件：前后端契约固定；配置可保存并生效；密钥不进入普通 JSON；旧 request 仍兼容。

### Wave 2：流水线增强

依次执行：

1. WP-103：第 3 步 LLM + 本地硬门禁。
2. WP-104：导演级分镜、提示词修正和复检。
3. WP-105：RunningHub LLM/G2 与比例实测。
4. WP-106：ComfyUI 分发背压。

退出条件：十阶段行为、预算和可恢复性通过后端测试；真实 provider 有证据。

### Wave 3：新 UI

依次执行：

1. WP-109：全新海滩工作壳和设计系统。
2. WP-110：一键、输入、导入和批量发起。
3. WP-111：真实十阶段、批次托盘和结果 dock。
4. WP-112：高级配置与 Prompt Profile UI。

退出条件：新源码不依赖旧页面；没有 demo ID；创建后不离开海滩壳；所有按钮有反馈。

### Wave 4：发布

1. 完成 WP-108 sidecar build 和安装包。
2. WP-113 端到端验收。
3. 删除旧产品路由与未使用 CSS。
4. 生成发布证据和回滚说明。

退出条件：真实单任务、三任务 batch、重启恢复、导出、断网 UI、安装包全部通过。

---

## 18. 第一个正式 Work Packet：WP-101

### 18.1 目标

在不重写现有 pipeline 的情况下，引入向后兼容的 RunRequest V2，并让新 UI 有稳定契约可依赖。

### 18.2 建议数据对象

1. `StoryInputSpec`
2. `CreationSpec`
3. `PromptProfileBinding`
4. `RenderBackendSpec`
5. `RunRequestV2`

### 18.3 输入模式

```text
auto
idea
requirements
script
mixed
```

`auto` 允许 content 为空。旧 `idea` 请求自动转换成 `input_spec.mode=idea`。

### 18.4 文件范围

优先限制在：

1. `relief_story_agent/models.py`
2. 新的 request normalization 模块，若复杂度需要。
3. `relief_story_agent/config_validation.py`
4. `relief_story_agent/orchestrator.py` 的输入适配边界。
5. `relief_story_agent/api.py`
6. 对应后端 tests。
7. `frontend/src/shared/contracts/` 的 V2 contract。
8. `frontend/src/shared/api/backendPayloads.ts` 和 tests。

不要在 WP-101 中重做视觉 UI、引入 Prompt Profile store 或实现 RunningHub provider。

### 18.5 必需测试

1. 旧 `idea` 请求仍能创建。
2. `auto` 空 content 合法。
3. `script` 空 content 非法。
4. 16:9、9:16 进入 creation spec。
5. ComfyUI endpoint 和 workflow path 不被前端转换丢失。
6. approval mode 正确映射。
7. batch defaults 正确应用 V2 字段。
8. Pydantic serialization 不包含密钥。
9. OpenAPI schema 与前端 contract 一致。

### 18.6 退出条件

1. 后端和前端测试全通过。
2. API 文档可见 V2 字段。
3. 旧请求兼容。
4. 无 UI 大改。
5. 一个独立提交和一个独立 PR。

---

## 19. 每个 Work Packet 的开发纪律

### 19.1 开始前

1. 从最新基线创建分支。
2. 写目标、非目标、契约、文件范围、测试。
3. 确认没有并行分支修改相同核心文件。

### 19.2 实施中

1. 先写失败测试或 contract test。
2. 小步修改。
3. 不做无关重构。
4. 每 30-60 秒向用户说明正在做什么和发现什么。
5. 遇到用户新消息，以最新消息为准。

### 19.3 完成前

1. 跑相关单元测试。
2. 跑全后端测试。
3. 跑前端 test 和 build。
4. UI 改动跑 Playwright 截图。
5. Desktop 改动跑 Node tests、launcher smoke 和打包 smoke。
6. 检查 `git diff --check`。
7. 检查 secrets 和机器路径。

### 19.4 PR 内容

1. 问题。
2. 方案。
3. 文件范围。
4. 测试证据。
5. 截图或真实运行证据。
6. 风险和回滚。
7. 明确未完成项。

---

## 20. 测试命令

### 20.1 后端

```powershell
python -m pytest -q relief_story_agent/tests tests
```

针对性示例：

```powershell
python -m pytest -q relief_story_agent/tests/test_pipeline.py
python -m pytest -q relief_story_agent/tests/test_prompt_workflow.py
python -m pytest -q relief_story_agent/tests/test_grid_image.py
python -m pytest -q relief_story_agent/tests/test_scheduler.py
```

### 20.2 前端

```powershell
Set-Location frontend
npm test
npm run typecheck
npm run build
```

### 20.3 Electron

以 GitHub `desktop/electron/src` 入口为准：

```powershell
Set-Location desktop\electron
npm test
npm run check
```

脚本以当前 package.json 为准；如果不存在 `test`，先运行已有的 Node tests，不要虚构通过。

### 20.4 Git

```powershell
git status --short --branch
git diff --check
git diff --cached --check
```

---

## 21. 本地开发启动

### 21.1 后端

开发默认：

```powershell
python -m relief_story_agent.server `
  --host 127.0.0.1 `
  --port 8891 `
  --state-dir relief_story_state `
  --model-config relief_story_agent/examples/model_config.local.example.json `
  --max-workers 2
```

### 21.2 前端

```powershell
Set-Location frontend
npm run dev
```

Vite 端口只用于开发。桌面成品不要求用户配置 5173/5174。

### 21.3 ComfyUI

默认 endpoint：

```text
http://127.0.0.1:8188
```

这是用户可配置的外部本地服务。不要把内部后端 8891 和 ComfyUI 8188 混为一谈。

### 21.4 Desktop

以最新 `desktop/electron/package.json` scripts 为准。GitHub master 使用 `src/main.js`，当前主工作区的 `main.cjs` 只是未提交实验。

---

## 22. 密钥与隐私

可能使用：

1. `RUNNINGHUB_API_KEY`
2. `GEMINI_API_KEY`
3. `DEEPSEEK_API_KEY`
4. `OPENAI_API_KEY`

规则：

1. 不读取后把密钥打印到终端或回复。
2. 不提交 `.env`。
3. 不写入普通 settings JSON。
4. 不写入 localStorage。
5. 不在错误栈中回显 Authorization header。
6. Desktop 使用 Electron safeStorage 或 Windows Credential Manager。
7. 后端只接收环境变量或受控进程注入。
8. 日志、诊断包和截图必须脱敏。

用户剧本、图片和视频也可能是私密数据。未经用户同意，不上传到非必要服务，不把真实正文放入 Git 测试夹具。

---

## 23. UI 验收矩阵

### 23.1 视口

1. 1280x800。
2. 1440x900。
3. 1920x1080。
4. 最小支持窗口 1040x720。
5. Windows 200% 缩放。

### 23.2 必查项

1. 海滩可见。
2. 中文字体一致。
3. 文本不溢出。
4. 按钮 loading 不改变布局。
5. 十阶段状态真实。
6. 批次托盘不遮挡主流程。
7. 抽屉焦点正确。
8. 键盘可操作。
9. reduced motion 生效。
10. 断网仍显示本地 UI 和产物。

### 23.3 禁止通过静态样例验收

必须使用真实 API 返回或明确的 test mock。生产 bundle 中不能存在 demo batch ID、静态“已完成”时间线或假四宫格来证明功能。

---

## 24. 后端验收矩阵

1. 旧 RunRequest 兼容。
2. V2 五种输入模式。
3. 第 3 步 LLM + 硬规则。
4. 第 2/3 步最多一次回炉。
5. 第 5/6 步最多一次修正和一次复检。
6. 第 6 步通过时 skipped。
7. FinalPromptPackage 可复现。
8. Prompt Profile 版本快照。
9. 16:9 2K 和 9:16 2K。
10. RunningHub 国内/国际站错误处理。
11. ComfyUI 幂等提交。
12. ComfyUI 并发 1。
13. 失败后从指定阶段重试。
14. 重启后 lease 恢复。
15. 产物 manifest 完整。

---

## 25. Desktop 验收矩阵

1. 双击启动。
2. 后端自动启动。
3. 端口冲突可恢复。
4. 启动失败有可读错误。
5. 工作流选择保存并重启后保留。
6. ComfyUI endpoint 保存并生效。
7. 密钥保存、状态和删除。
8. 打开日志目录。
9. 打开产物目录。
10. sidecar crash 后受控恢复。
11. 退出后无残留进程。
12. packaged frontend 不依赖 Vite。
13. packaged sidecar 可复现构建。

---

## 26. 已知高风险点

### 26.1 工作区治理

当前两个开发 worktree 都脏。任何自动 cleanup 都可能丢失用户数日工作。

### 26.2 本地候选与 GitHub 混淆

RunningHub 便捷 API、2K 比例和海滩 UI 在本地存在，不代表 GitHub master 已有。

### 26.3 四宫格校验冲突

当前 `validate_grid_image` 近似强制 1:1；产品已确认 16:9/9:16。必须修正，并用真实 provider 结果测试。

### 26.4 第 3 步不是 LLM

当前 `quality_gate` 只有本地规则。目标是 LLM 审查后再跑本地硬规则。

### 26.5 配置保存不等于生效

setup bundle 写文件后，运行中后端不会自动重载。必须有配置版本和生效握手。

### 26.6 Electron 两套入口

正式 `src/main.js` 与未提交 `main.cjs` 并存。必须以一个正式入口收敛。

### 26.7 旧 UI 回跳

本地海滩页创建后会跳回旧 review route。新 UI 必须原位进入运行态。

### 26.8 外部 API 不稳定

模型名、价格、站点 base URL、错误字段和响应可能变化。实现时查官方文档并用真实请求验证。

---

## 27. 不能宣称完成的内容

在没有证据前，不得说：

1. RunningHub 国内/国际全部模型已接入。
2. G2 横竖屏已真实成功。
3. 第 3 步已经是 LLM 审查。
4. 六阶段 Prompt Profile 已完成。
5. 配置保存后已热生效。
6. 安装包已携带可运行 sidecar。
7. 新 UI 已完成。
8. 批量三任务已真实生成视频。
9. 重启恢复已真实演练。
10. PR #3/#4 已合并，除非重新检查 GitHub。

---

## 28. Gemini 每次交付的回复格式

每个 Work Packet 完成后，用以下格式向用户报告：

```markdown
## 本次完成
- Work Packet：
- 用户可见变化：
- 后端变化：
- 前端变化：
- Desktop 变化：

## 修改文件
- `path`：原因

## 验证
- `command`：结果

## Git
- 分支：
- commit：
- PR：

## 尚未完成
- 明确列出

## 风险
- 明确列出

## 下一步
- 只列下一 Work Packet
```

不要用“基本完成”“应该可用”“看起来没问题”代替测试证据。

---

## 29. 推荐给 Gemini 的首轮任务文本

用户可以把下面这段与本文件一起交给 Gemini：

```text
请接手 Relief Story Agent。先完整阅读 AGENTS.md、GEMINI_3_5_FLASH_DEVELOPMENT_HANDOFF.md 和
docs/superpowers/specs/2026-06-29-relief-story-agent-beach-autopilot-development-spec-zh.md。

不要在 D:\codex工作区 当前脏工作树中直接开发，不要 reset、clean、stash all 或覆盖本地改动。
先 fetch GitHub，报告 master、PR #3、PR #4、所有 worktree 和 dirty 状态。然后基于最新 master 创建独立
worktree，运行后端与前端基线测试，编写 WP-101 的实施计划。计划必须限定文件范围、契约、兼容策略、
测试和退出条件。旧 UI 不继续修补；新 UI 以后从全新海滩工作台架构实现，只复用 API 和契约。

完成审计与计划后先向我报告，不要一次实现全部 Work Packet。
```

---

## 30. 最终 Definition of Done

项目只有同时满足以下条件才算完整：

1. Windows Desktop App 双击可用。
2. 后端、前端和 sidecar 自动协作。
3. 用户无需理解 8891、5173、5174。
4. ComfyUI 8188 可在高级设置修改并验证。
5. API key 可安全保存且不泄露。
6. 空白、灵感、要求、剧本和 mixed 输入可用。
7. 单条和批量创建可用。
8. 十阶段全部是真实状态。
9. 第 3 步是 LLM + 硬门禁。
10. 第 5/6 步有修正复检闭环。
11. G2/GPT Image 默认 2K，支持 16:9/9:16。
12. 四宫格和最终提示词真实进入 ComfyUI/LTX 2.3。
13. ComfyUI 队列稳定、幂等、可恢复。
14. 产物、日志、失败和恢复动作可见。
15. 新海滩 UI 不依赖旧页面结构。
16. 所有异步按钮有执行反馈。
17. 自动化测试、视觉测试、真实 provider、真实 ComfyUI 和安装包验收有证据。
18. GitHub master 的发布说明与真实能力一致。

在达到以上标准前，要准确报告剩余缺口，不要为了结束任务降低完成定义。
