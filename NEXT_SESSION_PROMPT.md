# 新会话接手提示词

把下面这段复制到新的 Codex 会话里即可：

```text
请继续开发本地项目：

D:\codex工作区

GitHub 仓库：

https://github.com/AharaOoO/relief-story-agent

目标：
逐步完成这个批量全自动短片生成 agent。UI 暂不优先，先打磨核心能力：多模型编剧、可迭代提示词模板、提示词漏洞检查、LTX 2.3 四宫格图、ComfyUI workflow 入队、批量任务恢复和本地部署诊断。工序顺序保持不变。

请先阅读：
1. PROJECT_HANDOFF.md
2. README.md
3. relief_story_agent/README.md
4. docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md
5. docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md

先运行：

git status --short --branch
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q

然后按计划实现 local_comfyui_smoke。实现时优先 TDD，不要跳过计划里的测试步骤。第一版只做 smoke runner：

- POST /api/smoke/comfyui
- python -m relief_story_agent.smoke_comfyui --request smoke_request.json
- dry-run 不上传、不入队
- real-run 上传四宫格图、patch LTX workflow、调用 ComfyUI /prompt
- 写出 smoke artifacts

不要做 UI，不要调用大模型，不要自动生成 ComfyUI 节点图，不要等待视频渲染完成，不要下载视频。

提交时不要 git add .，因为 D:\codex工作区 下面还有其他项目。只提交 relief-story-agent 相关文件。
```

## 接手后第一步

如果新会话需要一句更短的指令，可以用这个：

```text
读取 PROJECT_HANDOFF.md 和 docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md，按计划实现 local_comfyui_smoke，并在完成后运行 full test、commit、push。
```
