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

## 4. 当前最重要的下一步

下一阶段做 `local_comfyui_smoke`。

目标：验证“最终提示词产物 + 四宫格图 + 用户 LTX 2.3 workflow”能否真实进入本地 ComfyUI 并成功 `/prompt` 入队。

规格文档：

```text
docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md
```

实现计划：

```text
docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md
```

计划新增：

```text
relief_story_agent/smoke_comfyui.py
relief_story_agent/tests/test_smoke_comfyui.py
POST /api/smoke/comfyui
python -m relief_story_agent.smoke_comfyui --request smoke_request.json
```

第一版 smoke runner 只做：

- dry-run：预检、四宫格校验、workflow patch 预览、artifact 写出；
- real-run：上传四宫格图、patch workflow、调用 `/prompt`、记录 prompt id。

第一版不做：

- 不调用大模型；
- 不生成四宫格图；
- 不等待视频渲染完成；
- 不下载视频；
- 不做 UI。

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
docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md
docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md
```

再按计划实现 `local_comfyui_smoke`。

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
220 passed
```

最近已知提交：

```text
398f48e chore: prepare relief story agent handoff
```
