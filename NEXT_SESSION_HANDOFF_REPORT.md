# Relief Story Agent 下一会话完整交接报告

生成日期：2026-06-26
工作目录：`D:\codex工作区`
GitHub：`https://github.com/AharaOoO/relief-story-agent`
当前分支：`master`
生成时 HEAD：`55b24ed9d5686411ecc26af2472259f86b849f67` (`fix: require structured batch evidence`)

这份文件给下一个 Codex/AI 会话直接接力使用。它不是替代源码文档，而是把开发思路、当前进度、剩余计划、验收标准和执行建议收拢到一个文件里。新会话先读本文，再读 `PROJECT_HANDOFF.md` 和路线图。

## 1. 一句话目标

做一个本地部署优先的批量全自动短片生成 agent。当前不优先做 UI，先把后端核心跑实：多模型编剧、可迭代提示词模板、提示词漏洞检查、LTX 2.3 四宫格图、ComfyUI workflow 入队、批量任务恢复、本地部署诊断、真实视频产出和最终验收证据包。

内容定位是 60-120 秒“压力人群低刺激情绪缓冲短片”。目标不是泛泛鸡汤，也不是强刺激剧情，而是让观众有“被理解、可以慢一点、今天没那么糟”的感受。

## 2. 固定工序，不允许改顺序

任何开发、测试、恢复和验收都必须保留这条主链路：

```text
chief_screenwriter
-> deepseek_polish
-> quality_gate
-> gpt_prompt_writer
-> gpt_prompt_audit
-> gpt_prompt_reviser（最多一次）
-> final_prompts
-> four_grid_asset
-> artifacts
-> comfyui
```

关键边界：

- `quality_gate` 只放在 `deepseek_polish` 后面。
- `gpt_prompt_reviser` 最多自动执行一次，不能无限修。
- `four_grid_asset` 为 LTX 2.3 四宫格工作流准备参考图，可以手动覆盖，也可以由图像模型生成。
- `comfyui` 只 patch 用户提供的 workflow，不自动生成 ComfyUI 节点图。
- 用户 prompt 模板必须可替换，不能把用户模板写死进代码。

## 3. 开发思路复盘

整体策略是 local-first、API-first、evidence-first。

local-first：目标用户是在自己的 Windows 机器上运行，使用自己的 ComfyUI 整合包、workflow、模型 API key、输出目录。因此后端要优先解决本地路径、本地状态、本地诊断、ComfyUI 地址框、workflow 兼容和证据导出，而不是先做漂亮 UI。

API-first：所有核心能力先沉到 CLI 和 HTTP API，未来 UI/启动器只是调用这些 API。已经形成的接口包括 run、batch、diagnose、model-check、local-doctor、local-readiness、ComfyUI connect/discover/outputs、export、acceptance-status 等。

evidence-first：不能凭“流程看起来能跑”宣布完成。最终要靠真实模型返回、真实 ComfyUI 视频、本地 mp4、batch 产物、恢复演练、导出校验和 acceptance 报告来证明。最近几次提交都在加固这个原则。

开发原则：

- TDD：行为变化先写失败测试，再改实现。
- 小步提交：每个阶段 full test、commit、push。
- 不提交 secrets、`.env`、模型权重、私有 workflow、生成视频/图片。
- 不使用 `git add .`，因为 `D:\codex工作区` 下面还有其他项目。
- 不重复实现 `local_comfyui_smoke`。
- 不把 smoke `/prompt` 入队误报成真实视频完成。

## 4. 当前整体完成度

综合估算：后端约 70%。骨架、诊断、持久化、批量、恢复、ComfyUI 入队、artifact/export、本地验收框架已经比较厚实；但真实模型链路、真实视频下载、3-5 条真实 batch、重启恢复实操、最终 local-acceptance 证据还没跑完。

可以准确表达为：

- 后端 alpha 到 beta 之间，非 UI 核心框架已成型。
- 本地 ComfyUI smoke 已验证到 `/prompt` 入队。
- 还没有完成真实模型端到端。
- 还没有真实本地 mp4 产出证据。
- 还没有真实 3-5 条 batch 验收证据。
- 还不能说“除 UI 外基本完成”。

进度矩阵：

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 固定工序与 pipeline schema | 已完成 | `pipeline-schema` 可证明顺序和 invariants |
| 多模型 profile/stage 配置 | 已完成 | 支持 dry-run 和 real-run 小探针 |
| 模板检查 | 已完成 | writer/audit 模板占位符和 sha256 检查 |
| prompt writer/audit/reviser | 已完成 | reviser 最多一次 |
| LTX 2.3 workflow patch | 已完成 | 支持 LiteGraph/API JSON 常见注入点 |
| 四宫格资产准备/上传 | 已完成 | 支持手动图和图像模型链路 |
| ComfyUI `/upload/image`、`/object_info`、`/prompt` | 已完成 | 已有 real smoke 到 `/prompt` 证据 |
| ComfyUI output 查询/等待/下载 | 已完成 | 可按已有 `prompt_id` 查 `/history` 并下载 |
| 持久化 scheduler/batch/retry/pause/resume/cancel | 已完成 | 支持 state-dir 与恢复计划 |
| batch timeline/health/artifacts | 已完成 | 未来 UI 可直接消费 |
| export/zip/sha256/validate | 已完成 | 最近已加 batch_id 绑定校验 |
| local-bootstrap/doctor/setup/local-demo/local-acceptance/status/readiness | 已完成 | 本地部署诊断框架已成型 |
| 真实模型连接验收 | 未完成 | 等用户提供 API key/endpoint/model |
| 单条真实视频 | 未完成 | 未拿到真实 mp4 |
| 3-5 条真实 batch | 未完成 | 未跑真实 batch |
| 重启恢复真实演练 | 未完成 | 代码支持，缺真实演练证据 |
| 最终 release-ready 证据包 | 未完成 | `ready_for_release=true` 尚未达成 |

## 5. 最近提交与新增硬化

生成本文时最新几次提交：

```text
55b24ed fix: require structured batch evidence
0c21ca4 fix: require structured recovery evidence
709847b fix: bind export evidence to batch id
d570fac fix: require acceptance run and batch ids
eb3fe74 fix: revalidate preserved export evidence
```

这些提交的意义：

- `single_run=pass` 必须带顶层 `run_id` 和真实本地视频路径。
- `batch_run=pass` 必须带顶层 `batch_id`，并且附上结构化 `batch-artifacts` JSON。
- completed item 必须有 publish-ready 视频路径；failed item 必须有 `failed_stage` 和 `recommended_action.code`。
- `restart_recovery=pass` 必须带 before/after recovery-plan JSON，两个文件都要有 summary，且 `batch_id` 匹配顶层 `batch_id`。
- `export=pass` 必须有 export package validation report 和 zip validation report，且报告里的 `batch_id` 匹配顶层 `batch_id`。
- 旧 acceptance report 中保留的 pass 证据会被重新检查，不能靠过期文件或错误 batch 混过去。

## 6. 已完成能力清单

多模型与提示词链路：

- 多模型 profile / stage 配置。
- 模型 API key 通过环境变量引用，配置文件不写明文 key。
- OpenAI-compatible 文本模型调用层。
- retry、timeout、rate limit、attempt 记录、token/cost 统计。
- `model-check` dry-run / `--real-run`。
- `chief_screenwriter -> deepseek_polish -> quality_gate` 创作链。
- `gpt_prompt_writer -> gpt_prompt_audit -> gpt_prompt_reviser` 提示词链。
- writer/audit Markdown 模板可替换。
- `template-check` 检查占位符和 sha256。

LTX 2.3 / ComfyUI：

- 支持用户提供 workflow API JSON 或 LiteGraph JSON。
- LiteGraph LTX 注入点识别与 patch。
- 处理 LTX JSON 文本、RandomNoise seed、filename prefix、LoadImage 四宫格图、TD_LTXVAddGuideFromGrid、2x2 grid 等常见节点语义。
- real-run 会读取 `/object_info`，补齐前端 workflow 隐藏的 runtime-required widget 字段。
- 本地 ComfyUI 请求绕过环境代理，避免 `127.0.0.1` 被代理成 502。
- `connect-comfyui`、`discover-comfyui-workflows`、`smoke-comfyui`、`comfyui-outputs` 已具备。

批量、持久化、恢复：

- run/batch JSON 状态持久化。
- background scheduler、lease、expired running recovery。
- idempotency、retry、pause、resume、cancel。
- run/batch timeline、events、audit、health。
- recovery-plan 和 recover-batch dry-run。
- batch diagnostic endpoints 可容忍 child run 文件缺失，返回可诊断项。

artifact/export/acceptance：

- run manifest 与 batch artifact index。
- batch export：`publish_index.json`、`publish_index.csv`、`publish_videos/`、zip、sha256。
- export validate 和 zip validate。
- local-acceptance 收集 command outputs、summary、report、status、Markdown 报告。
- acceptance-status 会 overlay 完整发布矩阵。
- local-readiness 统一返回本地部署与验收阻塞项。

## 7. 当前明确不能宣称完成的部分

没有用户提供真实环境之前，不能诚实完成：

- Gemini 真实 `chief_screenwriter`。
- DeepSeek 真实 `deepseek_polish`。
- GPT 真实 prompt writer / audit / reviser。
- 图像模型真实四宫格生成。
- 单条 idea 到本地 mp4 的完整端到端。
- 3-5 条真实 batch。
- API 重启后的真实恢复演练。
- export + validate + zip validate 的真实发布包。
- `acceptance-status` 和 `local-readiness` 的 `ready_for_release=true`。

当前可以继续做：

- `compileall` / full pytest。
- fake-model `local-demo`。
- `template-check`。
- `model-check` dry-run。
- `diagnose`。
- `local-bootstrap` / `local-doctor` / `local-readiness`。
- ComfyUI endpoint / workflow 检查。
- smoke dry-run。
- 在已有手动四宫格图和本地 ComfyUI 时，smoke real-run 到 `/prompt`。
- 用已有 `prompt_id` 跑 `comfyui-outputs --wait --download`，但只有下载到真实视频才算视频证据。

## 8. 下一会话启动顺序

先运行：

```powershell
git status --short --branch
git pull --ff-only
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
```

然后阅读：

```text
PROJECT_HANDOFF.md
docs/superpowers/plans/2026-06-26-relief-story-agent-completion-roadmap.md
NEXT_SESSION_PROMPT.md
docs/LOCAL_DEPLOYMENT.md
relief_story_agent/README.md
NEXT_SESSION_HANDOFF_REPORT.md
```

如果这些文件与新鲜命令输出冲突，以新鲜命令输出为准。

## 9. P0：等待用户提供真实环境

需要用户提供：

- Gemini endpoint、model、API key 环境变量值。
- DeepSeek endpoint、model、API key 环境变量值。
- GPT 文本 endpoint、model、API key 环境变量值。
- 图像模型 endpoint、model、API key 环境变量值。
- 本地 ComfyUI 地址，通常是 `http://127.0.0.1:8188`。
- LTX 2.3 workflow JSON 路径。
- 输出目录，例如 `D:/relief_story_runs`。
- 最终验收目录，例如 `D:/relief_story_acceptance`。

环境变量只在 PowerShell 会话或用户自己的系统环境里设置，不能提交到仓库：

```powershell
$env:GEMINI_API_KEY = "<user supplied>"
$env:DEEPSEEK_API_KEY = "<user supplied>"
$env:OPENAI_API_KEY = "<user supplied>"
```

生成本地配置：

```powershell
relief-story-agent setup `
  --output-dir "D:/relief_story_config" `
  --workflow-path "<LTX 2.3 workflow json>" `
  --comfyui-endpoint "<ComfyUI endpoint>" `
  --output-root "D:/relief_story_runs" `
  --pretty
```

生成后编辑 `D:/relief_story_config/model_config.local.json` 里的非 secret 字段：base URL、model、profile 绑定。保留 `api_key_env`，不要写明文 key。

## 10. P1：真实模型连接验收

目标：证明 Gemini / DeepSeek / GPT 文本 / 图像模型配置真实可用。

命令：

```powershell
relief-story-agent model-check `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --real-run `
  --pretty
```

通过标准：

- `ready=true`。
- 每个 profile 都返回有效小 JSON 或有效图像 probe。
- 没有鉴权、endpoint、模型名、JSON contract 错误。

如果 provider response shape 与现有解析不兼容：先在 `relief_story_agent/tests/test_model_probe.py` 或 `test_model_runtime.py` 写失败测试，确认失败后再改生产代码。

## 11. P2：单条真实端到端视频

启动 API：

```powershell
relief-story-agent serve `
  --host 127.0.0.1 `
  --port 8891 `
  --state-dir "D:/relief_story_state" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --max-workers 1 `
  --comfyui-submission-concurrency 1
```

诊断：

```powershell
relief-story-agent diagnose `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --check-comfyui-connection `
  --pretty
```

创建真实 run：

```powershell
relief-story-agent run `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty
```

轮询：

```powershell
relief-story-agent run-status --server "http://127.0.0.1:8891" --run-id "{run_id}" --pretty
relief-story-agent run-timeline --server "http://127.0.0.1:8891" --run-id "{run_id}" --pretty
relief-story-agent run-artifacts --server "http://127.0.0.1:8891" --run-id "{run_id}" --pretty
```

如果 ComfyUI 已完成但 run artifact 没下载输出，用已有 `prompt_id` 单独刷新，不要盲目重新入队：

```powershell
relief-story-agent comfyui-outputs `
  --endpoint "<ComfyUI endpoint>" `
  --prompt-id "{prompt_id}" `
  --wait `
  --timeout-seconds 1200 `
  --poll-interval-seconds 5 `
  --artifact-dir "D:/relief_story_acceptance/comfyui_outputs" `
  --download `
  --pretty
```

通过标准：

- run `status=completed`。
- `final_storyboard` 非空。
- 四宫格图存在。
- ComfyUI `prompt_id` 存在。
- `actual_outputs` 有本地视频路径。
- mp4/mov/webm 等视频文件存在、非空、可打开，且容器签名可识别。

记录验收：

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "single_run" `
  --status "manual_pending" `
  --run-id "{run_id}" `
  --video-path "{local_video_path}" `
  --check "single_run=pass:run {run_id} completed with {local_video_path}" `
  --include-default-matrix `
  --pretty
```

注意：`single_run=pass` 没有 `--video-path` 或没有顶层 `run_id` 时，`acceptance-status` 必须继续阻塞。

## 12. P3：真实 batch 验收

目标：跑 3-5 条真实短片，单条失败不能拖垮整批。

先确认 `D:/relief_story_config/batch_request.full-ltx.json` 至少 3 个 item，最终建议 5 个。

预览：

```powershell
relief-story-agent batch-plan `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --check-comfyui-connection `
  --pretty
```

创建 batch：

```powershell
relief-story-agent batch `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty
```

轮询：

```powershell
relief-story-agent batch-status --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
relief-story-agent batch-timeline --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
relief-story-agent batch-health --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
relief-story-agent batch-artifacts --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty > "D:/relief_story_acceptance/batch_artifacts.json"
```

通过标准：

- 返回 `batch_id`。
- 每个 item 有 `run_id`。
- completed item 有 publish-ready 视频路径。
- failed item 有 `failed_stage` 和 `recommended_action.code`。
- batch artifact index 的 `batch_id` 匹配顶层验收 `batch_id`。

记录验收：

```powershell
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

## 13. P4：重启恢复演练

目标：batch queued/running 时停止 API，用同一个 `--state-dir` 重启，任务不丢，且不会盲目重复提交已被 ComfyUI 接受的任务。

停止 API 前保存 before plan：

```powershell
relief-story-agent recovery-plan `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --pretty > "D:/relief_story_acceptance/recovery_before_restart.json"
```

停止 API，然后用同一 state-dir 重启：

```powershell
relief-story-agent serve `
  --host 127.0.0.1 `
  --port 8891 `
  --state-dir "D:/relief_story_state" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --max-workers 1 `
  --comfyui-submission-concurrency 1
```

重启后检查：

```powershell
relief-story-agent scheduler --server "http://127.0.0.1:8891" --pretty
relief-story-agent batch-status --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
relief-story-agent recovery-plan `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --pretty > "D:/relief_story_acceptance/recovery_after_restart.json"
relief-story-agent recover-batch --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --dry-run --pretty
```

通过标准：

- batch 状态可查。
- recovery-plan 有 summary。
- queued/running/expired work 有明确 action。
- safe action 可 dry-run。
- 已接受的 ComfyUI submission 不被盲目重复提交。

记录验收：

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

## 14. P5：导出与校验

导出：

```powershell
relief-story-agent export-batch `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --export-root "D:/relief_story_exports" `
  --include-zip `
  --pretty
```

校验目录：

```powershell
relief-story-agent validate-export `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --export-dir "D:/relief_story_exports/{batch_id}" `
  --save-report `
  --pretty
```

校验 zip：

```powershell
relief-story-agent validate-export-zip `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --zip-path "D:/relief_story_exports/{batch_id}.zip" `
  --save-report `
  --pretty
```

通过标准：

- `publish_index.json` 存在。
- `publish_index.csv` 存在。
- `publish_videos/` 有 publish-ready 视频，且容器可识别。
- zip 存在。
- sha256 sidecar 存在。
- validation report `valid=true`。
- validation report 和 zip validation report 的 `batch_id` 都匹配顶层 `batch_id`。

记录验收：

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "export" `
  --status "manual_pending" `
  --batch-id "{batch_id}" `
  --check "export=pass:publish index, videos, zip, sha256, validation reports exist" `
  --include-default-matrix `
  --pretty
```

## 15. P6：最终本地验收证据包

运行：

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
  --smoke-dry-run `
  --comfyui-output-prompt-id "{prompt_id}" `
  --comfyui-output-artifact-dir "D:/relief_story_acceptance/comfyui_outputs" `
  --pretty
```

查询：

```powershell
relief-story-agent acceptance-status `
  --report "D:/relief_story_acceptance/acceptance_report.json" `
  --pretty

relief-story-agent local-readiness `
  --server "http://127.0.0.1:8891" `
  --acceptance-report "D:/relief_story_acceptance/acceptance_report.json" `
  --check-comfyui-connection `
  --comfyui-endpoint "<ComfyUI endpoint>" `
  --comfyui-workflow-path "<LTX 2.3 workflow json>" `
  --pretty
```

最终通过标准：

- `command_outputs/` 存在。
- `local_acceptance_summary.json` 存在。
- `acceptance_report.json` 存在。
- `acceptance_status.json` 存在。
- `ACCEPTANCE_REPORT.md` 存在。
- `pipeline_schema=pass`。
- `model-check --real-run` 通过。
- `single_run=pass` 有真实 `run_id` 和视频路径。
- `batch_run=pass` 有真实 `batch_id` 和 batch-artifacts 证据。
- `restart_recovery=pass` 有 before/after recovery-plan 证据。
- `export=pass` 有 export/zip validation 证据。
- `acceptance-status` 返回 `ready_for_release=true`。
- `local-readiness` 返回 `ready_for_real_runs=true` 和 `ready_for_release=true`。

只有这些都成立，才能说“除 UI 外基本完成”。

## 16. 代码修改建议

如果真实环境跑出问题，优先按下面顺序定位：

1. `model-check --real-run` 不通过：先修模型配置或 provider response parser。写 `test_model_probe.py` / `test_model_runtime.py` 回归测试。
2. `diagnose` 不通过：先看 suggested_actions，不要直接创建 run。
3. ComfyUI `/object_info` 或 workflow patch 不通过：优先检查用户 workflow、node class、widget map，不要自动生成节点图。
4. `/prompt` 接受但没有视频：用 `comfyui-outputs --wait --download` 查已有 `prompt_id`，不要盲目重复入队。
5. batch 卡住或恢复异常：先查 `scheduler`、`batch-health`、`recovery-plan`，再决定 `recover-batch --dry-run`。
6. acceptance-status 不 ready：按 blocking_checks 补证据，不要手改报告绕过。

每次行为修改必须：

```powershell
python -m pytest relief_story_agent/tests/<target_test_file>.py -q
git diff --check
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
```

然后只 stage 相关文件，例如：

```powershell
git add relief_story_agent/acceptance.py relief_story_agent/tests/test_acceptance.py docs/LOCAL_DEPLOYMENT.md PROJECT_HANDOFF.md NEXT_SESSION_PROMPT.md
git commit -m "<type>: <focused message>"
git push
```

不要使用：

```powershell
git add .
```

## 17. 文档与代码地图

优先阅读：

- `PROJECT_HANDOFF.md`：主交接文件，记录当前项目事实。
- `NEXT_SESSION_HANDOFF_REPORT.md`：本文，偏下一会话执行报告。
- `NEXT_SESSION_PROMPT.md`：短提示词，可直接贴给新会话。
- `docs/superpowers/plans/2026-06-26-relief-story-agent-completion-roadmap.md`：详细执行路线图。
- `docs/LOCAL_DEPLOYMENT.md`：本地部署操作说明。
- `relief_story_agent/README.md`：CLI/API 总说明。

核心代码：

- `relief_story_agent/pipeline.py`：固定工序 schema。
- `relief_story_agent/orchestrator.py`：主执行链。
- `relief_story_agent/model_config.py`、`model_probe.py`、`model_runtime.py`：模型配置与探针。
- `relief_story_agent/comfyui.py`、`ltx_workflow.py`、`comfyui_outputs.py`：ComfyUI 与 LTX workflow。
- `relief_story_agent/scheduler.py`、`storage.py`、`recovery.py`：持久化调度与恢复。
- `relief_story_agent/artifacts.py`：artifact、batch export、validate。
- `relief_story_agent/acceptance.py`、`local_acceptance.py`：验收证据。
- `relief_story_agent/local_runtime.py`：bootstrap、doctor、readiness。
- `relief_story_agent/api.py`：FastAPI routes。
- `relief_story_agent/cli.py`：统一 CLI。

测试重点：

- `relief_story_agent/tests/test_acceptance.py`
- `relief_story_agent/tests/test_local_acceptance.py`
- `relief_story_agent/tests/test_local_runtime.py`
- `relief_story_agent/tests/test_cli.py`
- `relief_story_agent/tests/test_artifacts.py`
- `relief_story_agent/tests/test_comfyui_outputs.py`
- `relief_story_agent/tests/test_batch_runs.py`
- `relief_story_agent/tests/test_scheduler.py`

## 18. 最容易踩的坑

- 把 ComfyUI smoke `/prompt` 入队误当成真实视频完成。
- 没有真实 `--video-path` 就标 `single_run=pass`。
- 没有 `batch-artifacts` JSON 就标 `batch_run=pass`。
- 没有 before/after recovery-plan 就标 `restart_recovery=pass`。
- export validation report 的 `batch_id` 与顶层 `batch_id` 不一致。
- 用过期的 acceptance report 或已删除的视频路径来宣称 ready。
- 把用户 API key 写入 repo。
- 自动生成 ComfyUI 节点图，偏离用户本地 workflow。
- 修改固定工序顺序。
- 在 `D:\codex工作区` 用 `git add .`。

## 19. 给下一会话的短指令

可以直接把下面这段发给下一会话：

```text
请接手 D:\codex工作区 的 relief-story-agent 项目。

先读：
1. NEXT_SESSION_HANDOFF_REPORT.md
2. PROJECT_HANDOFF.md
3. docs/superpowers/plans/2026-06-26-relief-story-agent-completion-roadmap.md
4. NEXT_SESSION_PROMPT.md
5. docs/LOCAL_DEPLOYMENT.md
6. relief_story_agent/README.md

先运行：
git status --short --branch
git pull --ff-only
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q

目标：继续完成本地部署优先的批量全自动短片生成 agent。UI 暂不优先。

固定工序不能改：
chief_screenwriter -> deepseek_polish -> quality_gate -> gpt_prompt_writer -> gpt_prompt_audit -> gpt_prompt_reviser（最多一次） -> final_prompts -> four_grid_asset -> artifacts -> comfyui

当前完成度：后端约 70%。骨架、批量、恢复、ComfyUI 入队、artifact/export、本地诊断和 acceptance 框架已成型；真实模型端到端、真实本地视频、3-5 条 batch、重启恢复演练、导出校验和最终 release-ready 证据还没完成。

下一步：等用户提供 Gemini / DeepSeek / GPT / 图像模型 API、本地 ComfyUI 地址、LTX 2.3 workflow 路径和输出目录后，按 P1-P6 执行：model-check --real-run -> 单条真实视频 -> 3-5 条 batch -> 重启恢复 -> export/validate -> local-acceptance。不要 git add .，不要提交 secrets。
```

## 20. 最终完成定义

以下全部有证据，才能对用户说“除 UI 外基本完成”：

- full tests 通过。
- `pipeline_schema=pass`。
- Gemini / DeepSeek / GPT 文本 / 图像模型 `model-check --real-run` 全部通过。
- 单条真实 run 完成，并有本地视频文件。
- 3-5 条 batch 完成或产生清晰可恢复/需人工处理的失败项。
- 重启恢复演练通过。
- batch export、directory validate、zip validate 通过。
- `local-acceptance` 生成完整证据包。
- `acceptance-status` 返回 `ready_for_release=true`。
- `local-readiness` 返回 `ready_for_release=true`。
- `PROJECT_HANDOFF.md` 或本文更新了真实 `run_id`、`batch_id`、artifact 目录、视频路径、export 路径和测试结果。
