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

注意：local_comfyui_smoke 已实现；真实本机 ComfyUI real-run 已通过 `/prompt` 入队验证。
另有 `relief-story-agent local-demo --output-dir "D:/relief_story_demo" --batch-size 2 --pretty` 可做无 API key、无 GPU 的离线编排骨架演练；`relief-story-agent local-acceptance --output-dir "D:/relief_story_acceptance" --repo-root "D:/codex工作区" --local-demo --model-config ... --run-request ... --batch-request ... --pretty` 可生成可查询的本地验收证据包。未来 UI/启动器可先读 `GET /api/local/bootstrap`，再调 `POST /api/local/setup-bundle` 生成本地配置包。
模板改动前可用 `relief-story-agent template-check --writer-template ... --audit-template ... --pretty` 校验占位符和模板指纹。
模型配置可用 `relief-story-agent model-check --model-config ... --pretty` dry-run 检查，或加 `--real-run` 发真实小探针。

最新 smoke 证据：

python -m relief_story_agent.smoke_comfyui --request "D:/relief_story_inputs/local_ltx_ready_smoke_request.real.json"
status=passed
ready=true
prompt_id=31037f9b-b8c8-5919-b717-fbe3c7e634eb
artifact_dir=D:\relief_story_smoke\comfyui_smoke_20260625T115742676759Z

最新全量测试：

python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
341 passed

最近核心功能提交包括：

a13a909 fix: bypass proxy for local ComfyUI calls
b487761 feat: add ComfyUI check to local doctor
5d7cb4c feat: add local doctor readiness report
522cd85 feat: validate execution policy stage names
96e3e82 feat: normalize ComfyUI endpoint inputs
3f1b70a feat: validate execution policy budgets
8102aae feat: add execution policy guardrails

新增补充：已有 ComfyUI prompt_id 时，可用 `relief-story-agent comfyui-outputs --endpoint "http://127.0.0.1:8188" --prompt-id "{prompt_id}" --artifact-dir "D:/relief_story_outputs/manual_check" --download --pretty` 或 `POST /api/comfyui/outputs` 查询/等待/下载输出；它只读 `/history`、`/queue`、`/view`，不会重新入队。

不要重复实现 smoke runner 或本地 ComfyUI 入队探针。优先从真实模型端到端继续；如果本地分支落后远端，先 `git pull --ff-only`。

接下来按总计划推进真实验收：

1. 补模板示例包、模型配置示例、真实 run/batch 请求示例。
2. 接真实 Gemini / DeepSeek / GPT 配置，跑单条端到端，拿到本地视频文件。
3. 跑 3-5 条 batch，验证恢复、导出和校验。
4. 写本地部署文档和最终验收报告。

不要优先做 UI，不要自动生成 ComfyUI 节点图，不要把用户模板写死在代码里，不要改变固定工序顺序。

提交时不要 git add .，因为 D:\codex工作区 下面还有其他项目。只提交 relief-story-agent 相关文件。
```

## 接手后第一步

如果新会话需要一句更短的指令，可以用这个：

```text
读取 docs/superpowers/plans/2026-06-25-full-auto-ltx-agent-productization.md，确认真实 ComfyUI smoke 已通过，然后从真实模型端到端和批量验收继续；每个阶段 full test、commit、push。
```
