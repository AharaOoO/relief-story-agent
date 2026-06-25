# Relief Story Agent

面向本地部署的批量全自动短片生成 agent。当前定位是 API-first 的多模型编排服务，用来稳定产出 60-120 秒“压力人群低刺激情绪缓冲短片”，并逐步打通 LTX 2.3 / ComfyUI 四宫格视频工作流。

## 当前主线

固定工序保持为：

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

其中：

- Gemini 侧定位为 `chief_screenwriter`，不是单一治愈模板，而是总编剧。
- DeepSeek 负责增强剧本细节和可看性，但不能提高刺激强度。
- GPT 负责按可迭代 Markdown 模板写分镜、提示词、漏洞检查和必要修正。
- ComfyUI 阶段读取用户提供的 workflow API/LiteGraph JSON，只替换声明字段并入队。
- LTX 2.3 四宫格工作流已设计并实现四宫格资产适配层。

## 交接入口

请先读：

- [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md)：项目进度、已完成能力、下一步计划、注意点。
- [relief_story_agent/README.md](relief_story_agent/README.md)：API、运行方式、配置说明。
- [docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md](docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md)：下一阶段真实 ComfyUI smoke runner 规格。
- [docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md](docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md)：下一阶段实现计划。

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

## 下一步

按计划实现 `local_comfyui_smoke`：

- `POST /api/smoke/comfyui`
- `python -m relief_story_agent.smoke_comfyui --request smoke_request.json`
- dry-run 不上传、不入队
- real-run 上传四宫格图、patch LTX workflow、调用 ComfyUI `/prompt`
- 写出 smoke artifacts 方便排错和交接

## GitHub 上传说明

当前工作区是 `D:\codex工作区`，里面有多个无关项目。这个仓库只应提交 Relief Story Agent 相关文件：

- `README.md`
- `PROJECT_HANDOFF.md`
- `pyproject.toml`
- `start_relief_story_agent.bat`
- `relief_story_agent/`
- `docs/superpowers/specs/`
- `docs/superpowers/plans/`

不要直接 `git add .`，避免把其他项目、模型产物或本地缓存一起传上去。
