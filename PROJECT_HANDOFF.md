# Relief Story Agent 项目交接说明

更新时间：2026-06-25
GitHub：<https://github.com/AharaOoO/relief-story-agent>
本地路径：`D:\codex工作区`

这份文档给下一个开发会话看。目标是让新会话不用翻聊天记录，也能知道项目做到哪、为什么这么设计、下一步怎么写代码。

## 1. 项目目标

做一个本地部署优先的批量全自动短片生成 agent。短期不急着做 UI，先把核心能力做扎实：

- 多模型编剧链路稳定；
- 提示词模板可迭代；
- 提示词漏洞检查可靠；
- LTX 2.3 四宫格图和 ComfyUI 工作流能跑通；
- 批量任务可恢复、可诊断；
- 后续能包装成粉丝也能本地部署的软件。

内容方向是 60-120 秒“压力人群低刺激情绪缓冲短片”。它不是泛泛“治愈短片”，也不是鸡汤励志，而是在很短时间里让观众感觉：被理解、能慢一点、今天没那么糟、世界还有一点柔软。

## 2. 固定工序

工序语义保持不变。后续可以升级执行框架，但不要随手改顺序。

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

各阶段职责：

- `chief_screenwriter`：Gemini 总编剧。负责选择内核、风格、系列方向、情绪曲线和完整剧本初稿。它不是“治愈模板生成器”。
- `deepseek_polish`：DeepSeek 改稿。增强戏剧性、动作、台词、细节和可看性，但不能增加强刺激、大吵大闹或压迫式冲突。
- `quality_gate`：剧本质量门禁。只放在 DeepSeek 改稿之后。
- `gpt_prompt_writer`：GPT 按用户可配置 Markdown 模板生成分镜、图像提示词、负面提示词和 LTX/ComfyUI 填充值。
- `gpt_prompt_audit`：GPT 按用户可配置 Markdown 模板检查提示词漏洞。
- `gpt_prompt_reviser`：如果 audit 发现问题，最多自动修正一次。
- `final_prompts`：最终可交给图像/视频链路的提示词产物。
- `four_grid_asset`：为 LTX 2.3 四宫格工作流准备四宫格参考图。
- `comfyui`：只替换声明字段，调用 ComfyUI `/prompt`。

## 3. 当前已完成能力

### 3.1 创作与提示词链路

已实现：

- 多模型阶段配置。
- `chief_screenwriter -> deepseek_polish -> quality_gate`。
- `gpt_prompt_writer -> gpt_prompt_audit -> gpt_prompt_reviser`。
- prompt writer 模板路径：`prompt_writer_template_path`。
- prompt audit 模板路径：`prompt_audit_template_path`。
- audit 失败时只自动修正一次。
- GPT Image 2 四宫格提示词长度控制，避免提示词过长。

需要守住的边界：

- 不要把用户提示词模板写死在代码里。
- 不要把自动修正改成无限循环。
- 不要让质量门禁提前拦截 Gemini 初稿。

### 3.2 ComfyUI / LTX 2.3 四宫格

已实现：

- ComfyUI workflow 分析。
- LiteGraph LTX 自动注入点识别。
- LiteGraph LTX widget patch 识别：支持常见整合包/`ComfyUI-LTXVideo` 示例 workflow，自动替换已有正向/负向 prompt、`RandomNoise` seed、`LoadImage` 文件名和 `SaveVideo`/`VHS_VideoCombine` 输出前缀；不生成节点、不改采样器、不重画工作流。
- LiteGraph real-run 会读取 ComfyUI `/object_info`，用运行时节点 schema 补齐 frontend workflow 里隐藏的必填 widget 值，包括 `PrimitiveInt`、`PrimitiveFloat`、loader 默认值、动态 combo 子字段等。
- 动态 combo 字段按 ComfyUI API 需要保留前缀，例如 `resize_type.longer_size`、`resize_type.shorter_size`、`resize_type.multiple`。
- 当 workflow 里的 COMBO 模型/LoRA 文件名不在本地整合包可用列表中时，会按 `/object_info` 的 options 做保守的运行时资产名兼容匹配；找不到可信匹配时保留原值，让 ComfyUI 或诊断明确报错。
- LTX payload 构造。
- workflow patch。
- ComfyUI `/upload/image`。
- ComfyUI `/prompt` 入队。
- 四宫格图生成/手动覆盖的统一资产模型。
- 四宫格图结构校验。
- 资源限流：图片生成和 ComfyUI 提交分开限流。

用户提供的 LTX 2.3 四宫格工作流关键节点已验证：

```text
node 202: LTX JSON 文本输入
node 37: RandomNoise seed
node 79: filename_prefix
node 196: LoadImage 四宫格图
node 221: TD_LTXVAddGuideFromGrid
grid shape: 2x2
```

### 3.3 批量、恢复、诊断

已实现：

- 本地持久化 scheduler。
- run / batch 状态存储。
- 模型配置和 API key 环境变量检查。
- 配置 validate / diagnose API。
- 失败分类。
- batch recovery plan。
- artifacts 和 manifest。
- ComfyUI 输出等待、取消、下载相关基础能力。
- `execution_policy` 运行时护栏，以及 preflight/diagnose 对总阶段预算和未知阶段名的提前校验。
- ComfyUI endpoint 地址框归一化：可接受 `127.0.0.1:8188`、尾斜杠和 `/queue` 粘贴输入，再统一连接本地 ComfyUI 根地址。
- 本地 ComfyUI HTTP 调用绕过环境代理，避免 Windows 代理把 `127.0.0.1:8188` 的 `/queue`、上传、`/prompt`、history/view 请求错误转发成代理 `502`。
- ComfyUI workflow 发现：`POST /api/comfyui/discover-workflows` 和 `relief-story-agent discover-comfyui-workflows` 可扫描本地整合包目录或 JSON 文件，识别可自动 patch 的 LTX workflow，并返回推荐路径给未来 UI/启动器。
- 已用本机 `D:/AI-Comfyui-onekey-V5/.../ComfyUI` 扫描验证：LTX 候选可返回 `adapter_mode=litegraph_ltx_widget_patch` 的 `recommended.path`，可作为后续地址框/工作流选择器的自动推荐来源。
- 机器可读 pipeline schema：`GET /api/pipeline/schema` 和 `relief-story-agent pipeline-schema --pretty` 可查询固定工序、阶段类型、可重试性、副作用和关键不变量。
- 单条 run 审计：`GET /api/runs/{run_id}/audit` 和 `relief-story-agent run-audit` 可检查事件序列、阶段顺序、未知阶段名和失败记录一致性。
- 本地 UI/bootstrap 契约：`GET /api/local/bootstrap` 和 `relief-story-agent local-bootstrap --pretty` 返回 API 端口、推荐 UI origin、CORS 白名单、默认 ComfyUI 地址和核心端点路径。
- 本地 doctor 就绪检查：`GET /api/local/doctor` 和 `relief-story-agent local-doctor` 返回模型环境、状态持久化、scheduler、资源限制和下一步建议；可选 `check_comfyui_connection=true` / `--check-comfyui-connection --comfyui-endpoint ...` 直接 ping 用户填入的本地 ComfyUI 地址。
- ComfyUI 连接检查会读取 `/object_info`，验证 workflow 需要的 node class 是否在当前本地 ComfyUI 运行时存在。缺节点时返回 `comfyui_node_types` 失败和 `install_or_enable_comfyui_nodes` 建议。
- 本地离线演练：`relief-story-agent local-demo --output-dir D:/relief_story_demo --batch-size 2 --pretty` 使用内置 fake model，关闭 ComfyUI 和图片生成，写出单条 run artifacts、batch 摘要、持久化重启恢复演练和 `local_demo_summary.json`；它只证明本地编排骨架、artifact 和恢复计划能跑通，不代表真实模型/真实视频验收完成。
- 本地 UI/启动器配置入口：`GET /api/local/bootstrap` 暴露推荐端口和核心 endpoint；`POST /api/local/setup-bundle` 接收 `output_dir`、`workflow_path`、`comfyui_endpoint`、`output_root`，写出与 `relief-story-agent setup` 相同的配置包，并且只保存环境变量名，不保存 API key。
- 本地验收证据收集器：`relief-story-agent local-acceptance` 会运行 `compileall`、全量 pytest，并可选用 `--local-demo` 收集离线演练证据、收集 `model-check`、run/batch `diagnose`、`smoke-comfyui`，落盘 `command_outputs/`、`local_acceptance_summary.json`、`acceptance_report.json` 和 `ACCEPTANCE_REPORT.md`，方便另一个 AI 或操作者核查当前进度。
- 模板迭代检查：`relief-story-agent template-check --writer-template ... --audit-template ...` 可在真实 run 前校验 Markdown 模板必需占位符、未知占位符和 sha256 指纹，减少模板改坏后才消耗模型额度的问题。
- 模型连接检查：`relief-story-agent model-check --model-config ...` 默认 dry-run 校验 profile、model 名和环境变量；`--real-run` 会对每个 profile 发一个极小 JSON 探针。API 入口为 `POST /api/config/model-check`，方便未来 UI 做“测试模型连接”按钮。

### 3.4 本地 ComfyUI smoke runner

已实现：

- `relief_story_agent/smoke_comfyui.py`。
- `POST /api/smoke/comfyui`。
- `python -m relief_story_agent.smoke_comfyui --request smoke_request.json`。
- dry-run：预检、四宫格校验、workflow patch 预览、artifact 写出，不上传、不入队。
- real-run：上传四宫格图、读取 `/object_info`、patch LTX workflow、调用 ComfyUI `/prompt`、记录 prompt id。
- real-run 写出的 `smoke_workflow_patched.json` 现在和实际 `/prompt` payload 同源，包含 runtime object_info 补出的动态字段和本机资产名兼容结果。
- mock ComfyUI 测试覆盖 dry-run、real-run、上传失败、prompt 失败、API、CLI。

真实本机 ComfyUI 已验证：

```text
endpoint: http://127.0.0.1:8188
workflow:
D:/AI-Comfyui-onekey-V5/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI/custom_nodes/ComfyUI-LTXVideo/example_workflows/2.3/LTX-2.3_ICLoRA_Motion_Track_Distilled.json

command:
python -m relief_story_agent.smoke_comfyui --request "D:/relief_story_inputs/local_ltx_ready_smoke_request.real.json"

result:
status=passed
ready=true
prompt_id=31037f9b-b8c8-5919-b717-fbe3c7e634eb
artifact_dir=D:\relief_story_smoke\comfyui_smoke_20260625T115742676759Z
post-check queue: {"queue_running": [], "queue_pending": []}
```

该 smoke 只证明上传和 `/prompt` 入队链路已被本机 ComfyUI 接受；没有等待渲染完成，也没有下载视频。

## 4. 当前最重要的下一步

`local_comfyui_smoke` 已经在本地完成，并已用真实本机 ComfyUI 跑通 real-run `/prompt` 入队。下一阶段不是重复实现 smoke runner，而是接真实模型链路和端到端验收。

目标：接入真实 Gemini / DeepSeek / GPT 模型配置，跑通单条端到端视频产出，再跑批量生成和恢复验收。

总开发计划：

```text
docs/superpowers/plans/2026-06-25-full-auto-ltx-agent-productization.md
```

smoke runner 规格记录：

```text
docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md
```

smoke runner 实现计划记录：

```text
docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md
```

下一阶段按这个顺序推进：

```text
1. 推送本次 ComfyUI runtime object_info / real-smoke 验证提交到 GitHub。
2. 补模板示例包、模型配置示例、真实 run/batch 请求示例。
3. 用真实 Gemini / DeepSeek / GPT 模型跑单条端到端，拿到本地视频文件。
4. 跑至少 3-5 条 batch，验证恢复、导出、校验。
5. 写部署文档和最终验收报告。
```

当前仍不能说“除了 UI 外已经完整做好”。原因是：真实模型链路、真实 ComfyUI 视频产出、批量真实验收、粉丝部署文档和配置体验还没有全部用证据跑完。

## 5. 文件地图

### 入口与配置

- `pyproject.toml`：包信息和依赖。
- `start_relief_story_agent.bat`：Windows 一键启动。
- `relief_story_agent/server.py`：命令行 server 入口。
- `relief_story_agent/api.py`：FastAPI 路由。
- `relief_story_agent/model_config.example.json`：模型配置示例。

### 核心流水线

- `relief_story_agent/orchestrator.py`：主编排。
- `relief_story_agent/models.py`：Pydantic 类型。
- `relief_story_agent/providers.py`：模型 provider。
- `relief_story_agent/model_runtime.py`：模型调用运行时。
- `relief_story_agent/prompt_templates.py`：模板渲染和默认模板。
- `relief_story_agent/quality.py`：剧本质量门禁。
- `relief_story_agent/output_contracts.py`：模型输出结构约束。

### ComfyUI / LTX

- `relief_story_agent/comfyui.py`：ComfyUI 分析、预览、提交、输出处理。
- `relief_story_agent/ltx_workflow.py`：LTX LiteGraph 注入点和 patch。
- `relief_story_agent/grid_image.py`：四宫格图提示词编译、校验、资产处理。
- `relief_story_agent/image_providers.py`：OpenAI-compatible 图片生成 provider。
- `relief_story_agent/resource_limits.py`：图片生成和 ComfyUI 提交限流。

### 可靠性与交付

- `relief_story_agent/scheduler.py`：本地持久化调度。
- `relief_story_agent/storage.py`：run/batch 存储。
- `relief_story_agent/failure_policy.py`：失败分类。
- `relief_story_agent/recovery.py`：恢复计划。
- `relief_story_agent/artifacts.py`：artifact、manifest、交付索引。
- `relief_story_agent/config_validation.py`：配置预检/诊断。
- `relief_story_agent/metrics.py`：统计和健康信息。

### 测试入口

- `relief_story_agent/tests/test_prompt_workflow.py`
- `relief_story_agent/tests/test_comfyui_mapping.py`
- `relief_story_agent/tests/test_grid_image.py`
- `relief_story_agent/tests/test_orchestrator.py`
- `relief_story_agent/tests/test_scheduler.py`
- `relief_story_agent/tests/test_artifacts.py`
- `relief_story_agent/tests/fixtures/ltx23_workflow_factory.py`

## 6. 新会话建议启动方式

另开会话后，建议直接复制 [NEXT_SESSION_PROMPT.md](NEXT_SESSION_PROMPT.md) 里的内容。

新会话先做三件事：

```powershell
cd D:\codex工作区
git status --short --branch
python -m pytest relief_story_agent/tests -q
```

然后阅读：

```text
PROJECT_HANDOFF.md
docs/superpowers/plans/2026-06-25-full-auto-ltx-agent-productization.md
docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md
docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md
```

再按总计划从真实 ComfyUI smoke 验收开始推进。

## 7. 验证命令

全量验证：

```powershell
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
```

下一阶段 smoke runner 的相关验证：

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py -q
python -m pytest relief_story_agent/tests/test_comfyui_mapping.py relief_story_agent/tests/test_grid_image.py relief_story_agent/tests/test_api.py -q
```

## 8. Git / GitHub 状态

仓库地址：

```text
https://github.com/AharaOoO/relief-story-agent
```

本地分支：

```text
master -> origin/master
```

当前仓库根目录是 `D:\codex工作区`。这个目录里还有很多无关项目，不要直接 `git add .`。

推荐提交范围：

```powershell
git add README.md PROJECT_HANDOFF.md NEXT_SESSION_PROMPT.md pyproject.toml start_relief_story_agent.bat relief_story_agent docs/superpowers .gitignore .gitattributes
```

不要提交：

- API key；
- 用户私有 workflow 原件；
- ComfyUI 输出；
- 视频、图片、模型权重；
- `.pytest_cache/`；
- `build/`；
- `*.egg-info/`；
- 其他项目目录。

## 9. 开发注意点

- 尽量走 TDD：先写失败测试，再实现。
- 保持模块边界清楚。不要把 smoke runner 写进 `api.py` 或 `comfyui.py` 里堆大函数。
- `dry_run=true` 必须无副作用：不上传、不入队。
- real-run 可以有副作用，但只到 `/prompt` 入队为止。
- ComfyUI workflow 只替换声明字段，不修用户节点图。
- LTX 四宫格工作流要保护注入点语义，不要硬编码只适配一个文件名。
- 后续可以研究 Temporal、Prefect、LangGraph 的工作流思想，但先不要引入重型依赖。
- 文档要跟代码一起更新。这个项目后续很依赖交接质量。

## 10. 最近基线

最近已知通过的验证：

```text
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
331 passed
```

最近已推送的核心功能提交：

```text
a13a909 fix: bypass proxy for local ComfyUI calls
b487761 feat: add ComfyUI check to local doctor
5d7cb4c feat: add local doctor readiness report
522cd85 feat: validate execution policy stage names
96e3e82 feat: normalize ComfyUI endpoint inputs
3f1b70a feat: validate execution policy budgets
8102aae feat: add execution policy guardrails
```
