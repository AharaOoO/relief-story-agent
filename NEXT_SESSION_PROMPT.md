# 新会话接手提示词

请接手本地项目：

```text
D:\codex工作区
```

GitHub 仓库：

```text
https://github.com/AharaOoO/relief-story-agent
```

先阅读唯一完整交接文件：

```text
PROJECT_HANDOFF.md
```

再阅读后续完成路线图：

```text
docs/superpowers/plans/2026-06-26-relief-story-agent-completion-roadmap.md
```

然后运行：

```powershell
git status --short --branch
git pull --ff-only
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
```

目标：继续完成这个批量全自动短片生成 agent。UI 暂不优先，先完成真实模型链路、真实本地 ComfyUI 视频产出、3-5 条 batch 验收、重启恢复、导出校验和最终 acceptance 证据包。

固定工序不能改：

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

重要边界：

- 没有用户提供 Gemini / DeepSeek / GPT / 图像模型 API key 前，不能真实跑通多模型端到端。
- 目前可以做 compile/test、fake-model `local-demo`、`template-check`、`model-check` dry-run、`diagnose`、ComfyUI 连接检查、smoke dry-run/real-run 到 `/prompt`。
- `local_comfyui_smoke` 已实现，不要重复造。
- 已新增 `GET /api/local/readiness` 和 `relief-story-agent local-readiness`，它是未来 UI/启动器“填 ComfyUI 地址后一键检查本地部署”的后端入口。
- 不要自动生成 ComfyUI 节点图，只使用用户本地已有 ComfyUI 整合包和用户提供的 workflow。
- 不要 `git add .`，因为 `D:\codex工作区` 下还有其他项目。只提交 relief-story-agent 相关文件。

下一步建议：

1. 等用户提供真实模型 API 和本地 ComfyUI/workflow 信息。
2. 跑 `model-check --real-run`。
3. 跑单条真实端到端，拿到本地 mp4，并用 `--video-path` 记录 `single_run` 验收。
4. 跑 3-5 条 batch。
5. 做重启恢复演练。
6. 做 batch export 和 validate。
7. 跑 `local-acceptance`，让 `acceptance-status` 和 `local-readiness` 都达到 `ready_for_release=true`；缺少单条视频路径会留下 `video_files` 阻塞项。
