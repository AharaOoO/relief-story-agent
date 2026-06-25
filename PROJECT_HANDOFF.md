# Relief Story Agent 项目交接说明

更新时间：2026-06-25

## 1. 项目目标

逐步完成一个可本地部署、可分享给粉丝使用的批量全自动短片生成 agent。UI 暂不优先，当前重点是核心链路专业、稳定、可恢复、可诊断。

目标作品类型是 60-120 秒“压力人群低刺激情绪缓冲短片”。内容不是泛泛治愈，也不是鸡汤励志，而是让观众感觉“被理解、可以慢一点、今天没那么糟、世界还有一点柔软”。

## 2. 固定工序

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

不能随意改变这个顺序。后续架构可以升级，执行框架可以大改，但工序语义保持不变。

## 3. 当前已完成能力

### 多模型创作链路

- `chief_screenwriter`：总编剧初稿，不局限治愈，可覆盖现实、奇幻、Q 版、误会反转、关系修复等风格。
- `deepseek_polish`：增强剧本反转、动作、台词、细节，但仍受低刺激约束。
- `quality_gate`：放在 DeepSeek 改稿后，检查内核、低刺激、共情、余味等。
- `gpt_prompt_writer`：按模板输出分镜、图像提示词、负面提示词、LTX/ComfyUI 填充值。
- `gpt_prompt_audit`：检查提示词漏洞，包括角色站位、空间关系、越轴、动态/静态画面逻辑、镜头含义。
- `gpt_prompt_reviser`：漏洞存在时只自动修正一次。

### 可迭代模板

- 支持 `prompt_writer_template_path`。
- 支持 `prompt_audit_template_path`。
- 模板是本地 UTF-8 Markdown 文件，方便持续替换升级。
- 未传模板时使用内置默认模板。

### ComfyUI / LTX 2.3 支持

- 支持用户提供 ComfyUI workflow JSON。
- 已能分析 LiteGraph LTX 工作流。
- 已识别用户 LTX 2.3 四宫格工作流关键节点：
  - node `202`：LTX JSON 文本输入
  - node `37`：RandomNoise seed
  - node `79`：输出 filename prefix
  - node `196`：四宫格 LoadImage
  - node `221`：`TD_LTXVAddGuideFromGrid`
  - grid shape：2x2
- 已设计并实现 `four_grid_asset` 阶段，包括自动/手动四宫格图、结构校验、上传、workflow patch。

### 批量与可靠性

- 有本地持久化 scheduler。
- 有模型配置和密钥环境变量检查。
- 有失败分类、恢复计划、批量健康报告、artifact index。
- 有资源限流：
  - image generation concurrency 默认 2
  - ComfyUI submission concurrency 默认 1

## 4. 关键文件索引

### 代码

- `relief_story_agent/server.py`：API server 入口。
- `relief_story_agent/api.py`：FastAPI 路由。
- `relief_story_agent/orchestrator.py`：主流水线编排。
- `relief_story_agent/models.py`：核心 Pydantic 类型。
- `relief_story_agent/comfyui.py`：ComfyUI workflow 分析、预览、提交、输出处理。
- `relief_story_agent/ltx_workflow.py`：LTX LiteGraph 自动注入点分析和 patch。
- `relief_story_agent/grid_image.py`：四宫格提示词编译、图片校验、资产处理。
- `relief_story_agent/image_providers.py`：OpenAI-compatible 图片生成 provider。
- `relief_story_agent/resource_limits.py`：图片生成和 ComfyUI 提交限流。
- `relief_story_agent/config_validation.py`：配置预检和诊断。
- `relief_story_agent/artifacts.py`：run/batch artifacts 和交付包索引。

### 文档规格

- `docs/superpowers/specs/2026-06-25-ltx23-grid-image-adapter-design.md`
- `docs/superpowers/plans/2026-06-25-ltx23-grid-image-adapter.md`
- `docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md`
- `docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md`

### 测试

- `relief_story_agent/tests/test_prompt_workflow.py`
- `relief_story_agent/tests/test_comfyui_mapping.py`
- `relief_story_agent/tests/test_grid_image.py`
- `relief_story_agent/tests/test_orchestrator.py`
- `relief_story_agent/tests/test_scheduler.py`
- `relief_story_agent/tests/test_artifacts.py`
- `relief_story_agent/tests/fixtures/ltx23_workflow_factory.py`

## 5. 下一阶段计划

下一阶段是实现 `local_comfyui_smoke`，目标是验证“最终提示词产物能否真实进入本地 LTX 2.3 ComfyUI workflow 并成功 `/prompt` 入队”。

规格：

- `docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md`

执行计划：

- `docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md`

计划新增：

- `relief_story_agent/smoke_comfyui.py`
- `POST /api/smoke/comfyui`
- `python -m relief_story_agent.smoke_comfyui --request smoke_request.json`
- `relief_story_agent/tests/test_smoke_comfyui.py`

## 6. 后续开发注意点

1. 不要把 prompt 模板写死在代码里。用户后续会持续迭代 `.md` 模板。
2. `gpt_prompt_reviser` 只自动修正一次，避免成本和时间失控。
3. GPT Image 2 四宫格提示词不要太长，合适即可，重点是四个关键帧清楚、角色一致、空间关系稳定。
4. ComfyUI workflow 只替换声明字段，不自动生成节点图，不随意改用户工作流。
5. 对 LTX 2.3 四宫格工作流，必须保护四个注入点：`196`、`202`、`37`、`79`。
6. dry-run 必须无副作用：不上传、不入队。
7. real-run 可以上传和 `/prompt`，但 local smoke 第一版不等待渲染完成、不下载视频。
8. 不要在当前仓库里提交 API key、模型权重、ComfyUI 输出、缓存、日志或用户私有 workflow 原件。
9. 当前根目录 `D:\codex工作区` 还有大量其他项目，Git 提交时不要 `git add .`。
10. 如果继续做架构升级，可以参考 Temporal 的 checkpoint/activity 思路、Prefect 的资源约束思路、LangGraph 的持久化思路，但第一阶段不要引入重型依赖。

## 7. 建议的验证命令

```powershell
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
```

若只验证下一阶段 smoke runner：

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py -q
python -m pytest relief_story_agent/tests/test_comfyui_mapping.py relief_story_agent/tests/test_grid_image.py relief_story_agent/tests/test_api.py -q
```

## 8. GitHub 上传建议

这个工作区不是一个干净单项目目录。建议 Git 仓库根目录仍放在 `D:\codex工作区`，但只 stage 下面这些文件：

```powershell
git add README.md PROJECT_HANDOFF.md pyproject.toml start_relief_story_agent.bat relief_story_agent docs/superpowers
```

不要上传：

- `football_data_studio/`
- `worldcup_player_intel_agent/`
- `hotspot_agent_control_center/`
- `SeedVR_OneClick_HD_Portable_v3_0/`
- LTX LoRA merge 输出目录
- `.pytest_cache/`
- `build/`
- `*.egg-info/`
- 日志、runs、outputs、ComfyUI 渲染产物

## 9. 当前限制

- GitHub CLI `gh` 当前未安装。
- 本地原 `.git` 目录此前是空目录，Git 认为它不是有效仓库。
- 若要自动创建 GitHub 仓库，需要安装并登录 `gh`，或提供一个已创建好的 GitHub remote URL。
