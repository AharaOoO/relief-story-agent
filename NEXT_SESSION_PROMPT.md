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
1. README.md
2. PROJECT_HANDOFF.md
3. docs/superpowers/plans/2026-06-25-full-auto-ltx-agent-productization.md
4. relief_story_agent/README.md
5. docs/superpowers/specs/2026-06-25-local-comfyui-smoke-design.md
6. docs/superpowers/plans/2026-06-25-local-comfyui-smoke.md

先运行：

git status --short --branch
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q

注意：local_comfyui_smoke 已在本地实现，最新本地提交是：

80da952 feat: add local ComfyUI smoke runner

如果 GitHub 还没包含这个提交，先确认本地状态并推送。不要重复实现 smoke runner。

接下来按总计划推进真实验收：

1. 用用户真实 LTX 2.3 workflow + 手动四宫格图跑 smoke dry-run。
2. 启动本地 ComfyUI 后跑 smoke real-run，确认 /prompt 返回 prompt_id。
3. 补模板示例包、模型配置示例、真实 run/batch 请求示例。
4. 接真实 Gemini / DeepSeek / GPT 配置，跑单条端到端。
5. 跑 3-5 条 batch，验证恢复、导出和校验。
6. 写本地部署文档和最终验收报告。

不要优先做 UI，不要自动生成 ComfyUI 节点图，不要把用户模板写死在代码里，不要改变固定工序顺序。

提交时不要 git add .，因为 D:\codex工作区 下面还有其他项目。只提交 relief-story-agent 相关文件。
```

## 接手后第一步

如果新会话需要一句更短的指令，可以用这个：

```text
读取 docs/superpowers/plans/2026-06-25-full-auto-ltx-agent-productization.md，确认 smoke runner 已推送，然后从真实 ComfyUI smoke 验收开始推进；每个阶段 full test、commit、push。
```
