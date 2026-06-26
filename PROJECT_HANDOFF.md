# Relief Story Agent 统一交接文件

更新日期：2026-06-26
本地路径：`D:\codex工作区`
GitHub 仓库：`https://github.com/AharaOoO/relief-story-agent`
当前分支：`master`

这份文件是给下一个 Codex/AI 会话看的单一交接入口。新会话先读这一份，再按里面列出的验证命令核对当前状态。不要依赖历史聊天记录。

## 1. 项目目标

做一个本地部署优先的批量全自动短片生成 agent。UI 不是当前优先级，核心是把后端链路打磨到粉丝可以在自己的 Windows 机器、自己的 ComfyUI 整合包、自己的模型 API key 上跑起来。

内容定位是 60-120 秒的“压力人群低刺激情绪缓冲短片”。不是泛泛的治愈鸡汤，也不是强刺激剧情。目标观感是：被理解、可以慢一点、今天没那么糟、世界还有一点柔软。

## 2. 固定工序，不能改顺序

工序顺序必须保持：

```text
chief_screenwriter
-> deepseek_polish
-> quality_gate
-> gpt_prompt_writer
-> gpt_prompt_audit
-> gpt_prompt_reviser (最多一次)
-> final_prompts
-> four_grid_asset
-> artifacts
-> comfyui
```

阶段职责：

- `chief_screenwriter`：Gemini 总编剧。负责故事内核、系列方向、风格、情绪曲线和剧本初稿。它不是单一“治愈模板生成器”。
- `deepseek_polish`：DeepSeek 改稿。增强戏剧性、细节、动作和可看性，但不能把内容推向高刺激、争吵、压迫或恐怖。
- `quality_gate`：剧本质量门禁。只放在 DeepSeek 后面。
- `gpt_prompt_writer`：GPT 按用户可替换 Markdown 模板生成分镜、图像提示词、负面提示词和 LTX/ComfyUI 输入。
- `gpt_prompt_audit`：GPT 按用户可替换 Markdown 模板检查角色站位、空间关系、越轴、动态画面逻辑、静态画面逻辑、镜头语言与剧情对应、每个镜头的叙事含义。
- `gpt_prompt_reviser`：如果 audit 不通过，最多自动修正一次。
- `final_prompts`：整理最终可进入图像/视频链路的提示词产物。
- `four_grid_asset`：为 LTX 2.3 四宫格工作流准备参考图。可手动覆盖，也可由图像模型生成。
- `artifacts`：记录脚本、分镜、提示词、模型调用、workflow patch、ComfyUI prompt id、输出文件和导出索引。
- `comfyui`：使用用户本地已有 ComfyUI 整合包及其节点，只 patch 用户提供的 workflow，不自动生成节点图。

## 3. 当前进度总览

整体后端进度约 65%。API-first 骨架、诊断、持久化、批量、ComfyUI 入队、部署辅助已经比较厚实；但真实模型端到端、真实视频下载、3-5 条批量验收、重启恢复演练和最终导出验收还没有用真实证据跑完。

可以说：

- 后端核心 alpha 已成型。
- 本地 ComfyUI `/prompt` 入队 smoke 已跑通。
- 还不能说“除 UI 外完整完成”。
- 真实端到端验收需要用户提供 Gemini / DeepSeek / GPT / 图像模型 API，并保证本地 ComfyUI + LTX 2.3 节点可用。

## 4. 已完成能力

### 4.1 多模型与提示词链路

- 多模型 profile / stage 绑定。
- 环境变量密钥检查，不把 API key 写入配置文件。
- OpenAI-compatible 文本模型调用层。
- 模型 retry、timeout、rate limit、attempt 记录和成本统计。
- `model-check` dry-run / `--real-run` 小探针。
- `chief_screenwriter -> deepseek_polish -> quality_gate` 创作链。
- `gpt_prompt_writer -> gpt_prompt_audit -> gpt_prompt_reviser` 提示词链。
- writer/audit Markdown 模板可由用户替换。
- `template-check` 可检查模板占位符和 sha256。
- 自动提示词修正最多一次。
- GPT Image 2 四宫格提示词做了长度约束，避免超长堆词。

### 4.2 LTX 2.3 / ComfyUI

- 支持用户提供的 workflow API JSON 或 LiteGraph JSON。
- 不自动生成 ComfyUI 节点图。
- LiteGraph LTX 注入点识别与 patch。
- 已覆盖常见 LTX 2.3 四宫格节点语义：
  - LTX JSON 文本输入
  - RandomNoise seed
  - filename prefix
  - LoadImage 四宫格图
  - TD_LTXVAddGuideFromGrid
  - 2x2 grid
- real-run 会读取 ComfyUI `/object_info`，补齐前端 workflow 隐藏的 runtime-required widget 字段。
- 动态 combo 子字段、PrimitiveInt/Float、loader 默认值、模型/LoRA COMBO 文件名兼容有处理。
- 本地 ComfyUI 请求绕过环境代理，避免 `127.0.0.1` 被代理成 502。
- `POST /api/comfyui/connect` 和 `relief-story-agent connect-comfyui` 可测 ComfyUI 地址。
- `POST /api/comfyui/discover-workflows` 和 `relief-story-agent discover-comfyui-workflows` 可扫描本地整合包 workflow。
- `POST /api/comfyui/outputs` 和 `relief-story-agent comfyui-outputs` 可在已有 `prompt_id` 时读取 `/history`、可选等待和下载，不重新入队。

### 4.3 local_comfyui_smoke

已实现：

- `relief_story_agent/smoke_comfyui.py`
- `POST /api/smoke/comfyui`
- `python -m relief_story_agent.smoke_comfyui --request smoke_request.json`
- dry-run：预检、四宫格图校验、workflow patch 预览、artifact 写出；不上传、不入队。
- real-run：上传四宫格图、读取 `/object_info`、patch LTX workflow、调用 ComfyUI `/prompt`、记录 `prompt_id`。

真实本机 smoke 证据：

```text
python -m relief_story_agent.smoke_comfyui --request "D:/relief_story_inputs/local_ltx_ready_smoke_request.real.json"
status=passed
ready=true
prompt_id=31037f9b-b8c8-5919-b717-fbe3c7e634eb
artifact_dir=D:\relief_story_smoke\comfyui_smoke_20260625T115742676759Z
```

注意：这个 smoke 只证明上传、patch、`/prompt` 入队被本地 ComfyUI 接受；它没有等待真实视频渲染完成，也没有下载视频。

### 4.4 批量、持久化、恢复、导出

- 本地持久化 scheduler。
- run / batch JSON 状态存储。
- run/batch idempotency。
- batch plan、batch create、pause、resume、cancel、retry。
- 失败分类与 recovery plan。
- batch diagnostic endpoints 可容忍 child run 文件缺失，返回 `inspect_missing_run`。
- `GET /api/runs/{run_id}/timeline` 和 `GET /api/batches/{batch_id}/timeline` 给未来 UI 用。
- artifact manifest。
- batch artifact index。
- batch export：publish index、publish videos、zip、sha256。
- export validate 和 zip validate。

### 4.5 本地部署与诊断

- `start_relief_story_agent.bat` Windows 一键启动入口。
- `GET /api/local/bootstrap` 和 `relief-story-agent local-bootstrap`。
- `GET /api/local/doctor` 和 `relief-story-agent local-doctor`。
- `POST /api/local/setup-bundle` 和 `relief-story-agent setup`。
- `relief-story-agent local-demo`：无 API key、无 GPU 的 fake model 离线演练。
- `relief-story-agent local-acceptance`：收集 compileall、pytest、pipeline-schema 固定工序、model-check、diagnose、local-demo、smoke、comfyui-output 等证据；ComfyUI 下载视频证据会检查本地文件存在、非空且有可识别的视频容器。
- 视频证据校验不会只信扩展名；MP4/MOV/M4V、WebM/MKV、AVI 都需要匹配基础容器签名。
- `single_run=pass` 必须同时记录真实本地视频路径；缺少 `--video-path` 时 `acceptance-status` 会保留 `video_files` 阻塞项并返回 `ready_for_release=false`。
- `single_run=pass` 还必须有顶层 `run_id`；`batch_run`、`restart_recovery` 和 `export=pass` 必须有顶层 `batch_id`，否则会重新阻塞发布。
- `restart_recovery=pass` 的 before/after recovery-plan 路径会在生成和刷新验收报告时重新读取；路径缺失、JSON 损坏、缺 summary 或 `batch_id` 不匹配都会变成 blocker，而不是 CLI traceback。
- 旧报告里保留的 `export=pass` 会重新检查 `details.validation_report` 和 `details.zip_validation_report`；报告缺失、JSON 无效、`valid=false` 或报告里的 `batch_id` 与顶层 `batch_id` 不一致，都会重新阻塞发布。
- `comfyui_outputs=pass` 也会重新检查结构化 `actual_outputs` 或 outputs report；下载视频路径缺失、已删除、为空或容器签名不可识别时都会重新阻塞发布。
- `model_check=pass` 也会重新检查记录的 model-check JSON；只有 `--real-run`、非空且全部 pass 的 checks、并包含 `image_provider` 探针时才算发布证据。
- `run_diagnose=pass` 和 `batch_diagnose=pass` 也会重新检查 diagnose JSON；`kind` 必须分别是 `run` / `batch`，且 `ready=true`。
- `pipeline_schema=pass` 也会重新检查 pipeline-schema JSON；固定工序顺序和 invariants 不满足时会重新阻塞发布。
- `full_tests=pass` 也会重新检查 pytest stdout 和 exit code；测试输出缺失、exit code 非 0 或出现 failed/errors 都会重新阻塞发布。
- `comfyui_dry_smoke=pass`、`comfyui_real_smoke=pass` 和 `local_demo=pass` 也会重新读取对应 `smoke_result.json` / `local_demo_summary.json` source；source 丢失或内容变坏时会重新阻塞发布。
- `acceptance` 生成报告时会写入完整发布矩阵，`acceptance-status` 读取旧报告时也会补齐缺失检查；只记录 smoke 或局部手工检查的报告不会被误判为 release-ready。
- `acceptance-status` 读取到损坏的 `acceptance_report.json` 时会返回 `acceptance_report` blocker，而不是崩溃或误判 ready。
- 本地 CLI 读取请求 JSON、smoke 请求 JSON 或模型配置 JSON 时，如果文件缺失、JSON 损坏或顶层不是 object，会返回结构化 `invalid_request` JSON，而不是 Python traceback。
- `connect-comfyui` 的请求 JSON 如果 schema 校验失败（例如无效 timeout），也会返回结构化 `invalid_request` JSON，而不是 Python traceback。
- `comfyui-outputs` 的请求 JSON 如果 schema 校验失败（例如缺少有效 `prompt_ids`），也会返回带 `path` 的结构化 `invalid_request` JSON，而不是缺少文件定位信息。
- `diagnose` 与 `model-check --run-request` 的请求 JSON 如果 schema 校验失败，也会返回结构化 `invalid_request` JSON，而不是 Python traceback。
- `relief-story-agent serve` / `relief-story-agent-server` 启动时如果 `--model-config` 无法加载，也会返回结构化 `invalid_request` JSON，方便 Windows 启动器显示文件级错误。
- `relief-story-agent acceptance-status` 和 `GET /api/local/acceptance-status`。
- `relief-story-agent local-readiness` 和 `GET /api/local/readiness`：本次新增，见下一节。

## 5. 本次新增：local-readiness

本次交接前新增了一个统一本地就绪度入口：

```http
GET /api/local/readiness
```

CLI：

```powershell
relief-story-agent local-readiness `
  --server "http://127.0.0.1:8891" `
  --acceptance-report "D:/relief_story_acceptance/acceptance_report.json" `
  --check-comfyui-connection `
  --comfyui-endpoint "127.0.0.1:8188/queue" `
  --comfyui-workflow-path "D:/ComfyUI/workflows/ltx23_four_grid.json" `
  --pretty
```

用途：

- 给未来 UI 或启动器一个“检查我的本地部署”的统一 JSON。
- 汇总 bootstrap、local-doctor、ComfyUI 地址检查、workflow 节点检查、acceptance-status 阻塞项。
- 返回 `ready_for_real_runs`、`ready_for_release`、`phase`、`checks`、`suggested_actions` 和 `ui_contract`。
- `ready_for_real_runs` 要求 local-doctor 没有 fail 也没有 warn；缺模型 profile、非持久 state 或未挂 scheduler 不能被误报为可无人值守真实运行。
- `summary.real_run_blocking_count` 统计阻塞真实运行的本地部署检查；`summary.release_blocking_count` 统计阻塞发布的所有非 pass 检查。
- `ui_contract` 明确未来 UI 里 ComfyUI 地址框、workflow 路径框、验收报告路径对应的参数和后端端点。

边界：

- 不调用大模型。
- 不上传图片。
- 不入队 ComfyUI。
- 不等待视频。
- 不下载视频。

相关文件：

- `relief_story_agent/local_runtime.py`
- `relief_story_agent/api.py`
- `relief_story_agent/cli.py`
- `relief_story_agent/setup_wizard.py`
- `relief_story_agent/tests/test_local_runtime.py`
- `relief_story_agent/tests/test_cli.py`
- `relief_story_agent/tests/test_setup_wizard.py`
- `docs/LOCAL_DEPLOYMENT.md`
- `relief_story_agent/README.md`

## 6. 用户未提供模型 API 前能做什么

可以做：

- `python -m compileall -q relief_story_agent`
- `python -m pytest relief_story_agent/tests -q`
- `relief-story-agent local-demo`
- `relief-story-agent template-check`
- `relief-story-agent model-check` dry-run
- `relief-story-agent diagnose`
- `relief-story-agent local-bootstrap`
- `relief-story-agent local-doctor`
- `relief-story-agent local-readiness`
- ComfyUI endpoint / workflow 检查
- smoke dry-run
- 如果已有手动四宫格图和本地 ComfyUI，可跑 smoke real-run 到 `/prompt` 入队

不能诚实完成：

- Gemini 真实 `chief_screenwriter`
- DeepSeek 真实 `deepseek_polish`
- GPT 真实 prompt writer / audit / reviser
- GPT Image 或兼容图像模型真实生成四宫格图
- 真实单条 run 从 idea 到本地 mp4
- 真实 3-5 条 batch 验收
- 最终“除 UI 外完成”声明

## 7. 还缺什么

### P0：等待用户提供真实模型 API 与本地环境

需要用户给：

- Gemini 或兼容 OpenAI endpoint、model、`GEMINI_API_KEY`
- DeepSeek endpoint、model、`DEEPSEEK_API_KEY`
- GPT 文本模型 endpoint、model、`OPENAI_API_KEY`
- 图像模型 endpoint、model，可用 GPT Image 2 或兼容服务
- 本地 ComfyUI 地址，默认 `http://127.0.0.1:8188`
- 可用 LTX 2.3 workflow 路径
- 本地输出目录

### P1：真实模型连接验收

目标：证明模型配置真的可用。

命令：

```powershell
relief-story-agent model-check `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --real-run `
  --pretty
```

验收标准：

- `ready=true`
- 每个 profile 至少一次小 JSON 探针成功
- 不返回鉴权、模型名、endpoint 或 JSON contract 错误

### P2：单条真实端到端视频

目标：从 idea 自动跑完完整工序并拿到本地视频文件。

流程：

```powershell
relief-story-agent diagnose `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --check-comfyui-connection `
  --pretty

relief-story-agent run `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty
```

轮询：

```powershell
relief-story-agent run-status --run-id "{run_id}" --pretty
relief-story-agent run-timeline --run-id "{run_id}" --pretty
relief-story-agent run-artifacts --run-id "{run_id}" --pretty
```

验收标准：

- run `status=completed`
- `final_storyboard` 非空
- 四宫格图存在
- ComfyUI prompt id 存在
- `actual_outputs` 中有本地视频路径
- mp4 文件存在且可打开

### P3：真实 batch 验收

目标：至少 3 条，最好 5 条，连续批量生成，单条失败不拖垮整批。

流程：

```powershell
relief-story-agent batch-plan `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --check-comfyui-connection `
  --pretty

relief-story-agent batch `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty
```

验收标准：

- 返回 `batch_id`
- 每个 item 有 `run_id`
- 批量汇总正确
- 失败项可诊断，可重试或进入 manual blocker
- 成功项进入 publish-ready
- `batch_run=pass` 必须带 `batch-artifacts` JSON 证据，且报告的 `batch_id` 匹配顶层 `batch_id`；完成项要有 publish-ready 视频路径，失败项要有 `failed_stage` 和 `recommended_action.code`。

记录验收时使用：

```powershell
relief-story-agent batch-artifacts --batch-id "{batch_id}" --pretty > "D:/relief_story_acceptance/batch_artifacts.json"
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "batch_run" `
  --status "manual_pending" `
  --batch-id "{batch_id}" `
  --check "batch_run=pass:batch {batch_id} produced item summaries and publish-ready outputs" `
  --batch-artifacts-report "D:/relief_story_acceptance/batch_artifacts.json" `
  --include-default-matrix `
  --pretty
```

### P4：重启恢复演练

目标：API 中途关闭后，用同一个 `state-dir` 重启，任务不丢。

步骤：

1. batch queued/running 时先保存 before-restart recovery plan。
2. 停止 API。
3. 用同一 `--state-dir` 重启 API。
4. 调：

```powershell
relief-story-agent recovery-plan --batch-id "{batch_id}" --pretty > "D:/relief_story_acceptance/recovery_before_restart.json"
# Stop and restart the API with the same --state-dir, then:
relief-story-agent scheduler --pretty
relief-story-agent batch-status --batch-id "{batch_id}" --pretty
relief-story-agent recovery-plan --batch-id "{batch_id}" --pretty > "D:/relief_story_acceptance/recovery_after_restart.json"
relief-story-agent recover-batch --batch-id "{batch_id}" --dry-run --pretty
```

验收标准：

- batch 状态仍可查。
- queued/running/expired work 有明确 recovery plan。
- safe recovery action 可 dry-run。
- 不盲目重新提交 ComfyUI 已接受任务。
- `restart_recovery=pass` 必须带结构化 before/after recovery-plan 证据，且两个 plan 的 `batch_id` 都要匹配顶层 `batch_id`。

记录验收时使用：

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "restart_recovery" `
  --status "manual_pending" `
  --batch-id "{batch_id}" `
  --check "restart_recovery=pass:batch {batch_id} survived restart and recovery-plan was queryable" `
  --restart-recovery-before-report "D:/relief_story_acceptance/recovery_before_restart.json" `
  --restart-recovery-after-report "D:/relief_story_acceptance/recovery_after_restart.json" `
  --include-default-matrix `
  --pretty
```

### P5：导出与校验

目标：把 batch 结果打成可发布/可分享包。

命令：

```powershell
relief-story-agent export-batch `
  --batch-id "{batch_id}" `
  --export-root "D:/relief_story_exports" `
  --include-zip `
  --pretty

relief-story-agent validate-export `
  --batch-id "{batch_id}" `
  --export-dir "D:/relief_story_exports/{batch_id}" `
  --save-report `
  --pretty

relief-story-agent validate-export-zip `
  --batch-id "{batch_id}" `
  --zip-path "D:/relief_story_exports/{batch_id}.zip" `
  --save-report `
  --pretty
```

验收标准：

- `publish_index.json`
- `publish_index.csv`
- `publish_videos/` 非空且容器可识别的 publish 视频
- zip
- sha256
- validation report `valid=true`

### P6：最终本地验收证据包

命令：

```powershell
relief-story-agent local-acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --repo-root "D:/codex工作区" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --batch-request "D:/relief_story_config/batch_request.full-ltx.json" `
  --local-demo `
  --model-check-real-run `
  --smoke-request "D:/relief_story_config/smoke_request.json" `
  --comfyui-output-prompt-id "{prompt_id}" `
  --comfyui-output-artifact-dir "D:/relief_story_acceptance/comfyui_outputs" `
  --pretty
```

验收标准：

- `command_outputs/`
- `local_acceptance_summary.json`
- `acceptance_report.json`
- `acceptance_status.json`
- `ACCEPTANCE_REPORT.md`
- `ready_for_release=true`

`local-acceptance` 会保留同一输出目录里旧 `acceptance_report.json` 中已经 pass 的检查、顶层 `run_id` / `batch_id` 和视频路径；如果本次运行产生同名检查，则以本次结果为准。ComfyUI output download 检查只有在本地视频文件存在、非空且有可识别的视频容器时才会通过。导入的 `smoke_result.json` / `local_demo_summary.json` 会先转成检查项再计算顶层 status，source 文件不 ready 时不会留下 completed 包。保留下来的 `video_paths` 也会在计算顶层 status 前按当前磁盘状态重新检查，旧 mp4 丢失或不可打开时不会留下 completed 包。`single_run=pass` 如果没有视频路径证据，`acceptance-status` 会新增/保留 `video_files` 阻塞项；如果报告已有 `video_paths`，`local-acceptance` 和 `acceptance-status` 都不信任旧的 `video_files=pass`。`single_run=pass` 缺顶层 `run_id`，或 `batch_run` / `restart_recovery` / `export=pass` 缺顶层 `batch_id`，都会重新阻塞发布；`restart_recovery=pass` 还会要求 before/after recovery-plan 证据存在、JSON 有效、有 summary，且两个 plan 的 `batch_id` 与顶层 `batch_id` 一致；`export=pass` 还会要求包验证报告和 zip 验证报告的 `batch_id` 与顶层 `batch_id` 一致。`acceptance` 和 `acceptance-status` 都会补齐完整发布矩阵，缺失的 P2-P6 证据都会保持阻塞；报告顶层 status 不是 completed 时，即使单项检查都 pass，也会返回 `overall_status` 阻塞项。这样 P2-P5 手动记录的真实单条、batch、恢复、导出证据不会在最终 P6 重跑时丢失。

只有这一步和真实视频、真实 batch、真实导出都通过，才能说“除 UI 外基本完成”。

## 8. 后续详细计划文件

新的后续完成路线图写在：

```text
docs/superpowers/plans/2026-06-26-relief-story-agent-completion-roadmap.md
```

继续开发时优先按这个计划拆任务。旧总计划仍保留：

```text
docs/superpowers/plans/2026-06-25-full-auto-ltx-agent-productization.md
```

## 9. 新会话启动指令

把下面这段给新会话：

```text
请接手 D:\codex工作区 的 relief-story-agent 项目。
先阅读 PROJECT_HANDOFF.md，这是当前唯一完整交接文件。
再运行：
git status --short --branch
git pull --ff-only
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q

目标：继续完成批量全自动短片生成 agent。UI 暂不优先。
固定工序不能改：
chief_screenwriter -> deepseek_polish -> quality_gate -> gpt_prompt_writer -> gpt_prompt_audit -> gpt_prompt_reviser(最多一次) -> final_prompts -> four_grid_asset -> artifacts -> comfyui。

注意：当前在没有真实模型 API key 前，只能做 dry-run、fake-model demo、diagnose、ComfyUI smoke、readiness 和单元/集成测试；不能宣称真实端到端完成。
下一步等用户提供 Gemini / DeepSeek / GPT / 图像模型 API 后，先跑 model-check --real-run，再跑单条真实端到端视频，然后 3-5 条 batch、重启恢复、导出校验和 local-acceptance。
不要 git add .，只提交 relief-story-agent 相关文件。
```

## 10. Git 注意事项

仓库根目录是 `D:\codex工作区`，里面还有其他项目。不要使用：

```powershell
git add .
```

只提交本项目相关文件，例如：

```powershell
git add README.md PROJECT_HANDOFF.md NEXT_SESSION_PROMPT.md pyproject.toml start_relief_story_agent.bat relief_story_agent docs
```

不要提交：

- API key
- 私有 workflow 原文件
- ComfyUI 输出视频/图片
- 模型权重
- `.pytest_cache/`
- `build/`
- `*.egg-info/`
- 其他项目目录

## 11. 当前关键命令速查

启动 API：

```powershell
relief-story-agent serve --host 127.0.0.1 --port 8891 --state-dir "D:/relief_story_state"
```

本地 bootstrap：

```powershell
relief-story-agent local-bootstrap --pretty
```

本地 doctor：

```powershell
relief-story-agent local-doctor `
  --server "http://127.0.0.1:8891" `
  --check-comfyui-connection `
  --comfyui-endpoint "127.0.0.1:8188/queue" `
  --comfyui-workflow-path "D:/ComfyUI/workflows/ltx23_four_grid.json" `
  --pretty
```

统一 readiness：

```powershell
relief-story-agent local-readiness `
  --server "http://127.0.0.1:8891" `
  --acceptance-report "D:/relief_story_acceptance/acceptance_report.json" `
  --check-comfyui-connection `
  --comfyui-endpoint "127.0.0.1:8188/queue" `
  --comfyui-workflow-path "D:/ComfyUI/workflows/ltx23_four_grid.json" `
  --pretty
```

模型检查：

```powershell
relief-story-agent model-check --model-config "D:/relief_story_config/model_config.local.json" --pretty
relief-story-agent model-check --model-config "D:/relief_story_config/model_config.local.json" --run-request "D:/relief_story_config/run_request.full-ltx.json" --real-run --pretty
```

模板检查：

```powershell
relief-story-agent template-check `
  --writer-template "D:/relief_story_config/templates/prompt_writer.default.md" `
  --audit-template "D:/relief_story_config/templates/prompt_audit.default.md" `
  --pretty
```

本地离线演练：

```powershell
relief-story-agent local-demo --output-dir "D:/relief_story_demo" --batch-size 2 --pretty
```

ComfyUI smoke：

```powershell
relief-story-agent smoke-comfyui --request "D:/relief_story_config/smoke_request.json" --dry-run
relief-story-agent smoke-comfyui --request "D:/relief_story_config/smoke_request.json"
```

## 12. 本次交接前验证

提交前必须重新运行：

```powershell
git diff --check
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
```

如果下一会话看到本文和实际命令输出不一致，以新鲜命令输出为准。
