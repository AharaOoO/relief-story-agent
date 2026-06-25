# Relief Story Agent

本仓库是一个本地部署优先的短片生成 agent。当前目标不是先做漂亮 UI，而是把核心流水线打磨稳定：多模型编剧、提示词模板迭代、提示词漏洞检查、LTX 2.3 四宫格图、ComfyUI 工作流入队、批量任务与恢复能力。

项目正在逐步走向“可以分享给粉丝本地部署使用”的软件形态。现在最重要的是让下一个开发会话能快速接手，不需要翻长聊天记录。

## 先读这几个文件

1. [docs/superpowers/plans/2026-06-25-full-auto-ltx-agent-productization.md](docs/superpowers/plans/2026-06-25-full-auto-ltx-agent-productization.md)
   完整开发计划：需求复述、真实进度、完成定义、阶段任务、验收标准和交接指令。

2. [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md)
   当前进度、核心架构、已完成能力、未完成事项、开发注意点。

3. [NEXT_SESSION_PROMPT.md](NEXT_SESSION_PROMPT.md)
   另开 Codex 会话时直接复制这段，让新会话快速进入状态。

4. [relief_story_agent/README.md](relief_story_agent/README.md)
   API、配置、启动方式、模板、ComfyUI 支持说明。

5. [docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md](docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md)
   `local_comfyui_smoke` 的规格记录。

6. [docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md](docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md)
   已实现 smoke runner 的 TDD 计划记录。

## 当前固定工序

工序顺序不要随意改：

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

简要理解：

- `chief_screenwriter`：Gemini 总编剧，负责内核、风格、系列方向、情绪曲线和初稿。
- `deepseek_polish`：DeepSeek 增强剧本细节，但不能提高刺激强度。
- `quality_gate`：只在 DeepSeek 改稿后做剧本质量门禁。
- `gpt_prompt_writer`：根据可配置 Markdown 模板生成分镜、图像提示词、负面提示词和 LTX/ComfyUI 填充值。
- `gpt_prompt_audit`：根据可配置 Markdown 模板检查角色站位、空间关系、越轴、动态/静态画面逻辑、镜头含义。
- `gpt_prompt_reviser`：最多自动修正一次。
- `four_grid_asset`：为 LTX 2.3 四宫格工作流准备、校验、上传参考图。
- `comfyui`：只替换声明字段并调用 ComfyUI。

## 本地启动

Windows 推荐：

```powershell
.\start_relief_story_agent.bat
```

开发模式：

```powershell
python -m pip install -e .
python -m relief_story_agent.server --host 127.0.0.1 --port 8891
```

健康检查：

```http
GET http://127.0.0.1:8891/api/health
```

## 当前验证基线

最近一次本地完整验证：

```text
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
298 passed
```

## 下一步开发

`local_comfyui_smoke` 已实现并推送。最近核心功能提交包括：

```text
522cd85 feat: validate execution policy stage names
96e3e82 feat: normalize ComfyUI endpoint inputs
3f1b70a feat: validate execution policy budgets
8102aae feat: add execution policy guardrails
```

下一步从真实本机联调开始：

- 用用户真实 LTX 2.3 workflow 和手动四宫格图跑 dry-run。
- 启动本地 ComfyUI 后跑 real-run，确认 `/prompt` 返回 prompt id。
- 再接真实 Gemini / DeepSeek / GPT 模型配置，跑单条端到端。
- 最后做批量验收、导出验收、部署文档和非 UI 的本地使用体验。

完整执行计划在：

```text
docs/superpowers/plans/2026-06-25-full-auto-ltx-agent-productization.md
```

## GitHub / Git 注意

这个仓库位于 `D:\codex工作区`。该目录下还有很多其他项目，所以不要直接 `git add .`。

本仓库只应该跟踪：

```text
README.md
PROJECT_HANDOFF.md
NEXT_SESSION_PROMPT.md
pyproject.toml
start_relief_story_agent.bat
relief_story_agent/
docs/superpowers/specs/
docs/superpowers/plans/
.gitignore
.gitattributes
```

GitHub 仓库：

```text
https://github.com/AharaOoO/relief-story-agent
```
