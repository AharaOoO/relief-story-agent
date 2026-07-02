# Autopilot Backend Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐六阶段提示词、质量门禁模型、RunningHub convenience LLM/G2 和新工作台所需的稳定 API 契约。

**Architecture:** 保留现有 `StoryRunOrchestrator`、scheduler 和持久化模型；新增独立 provider/router 与 API schema。外部服务差异在 provider 层归一化，run snapshot 保存最终解析后的模型、提示词和图像配置。

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, httpx/OpenAI SDK, pytest

---

### Task 1: 冻结六阶段模型与站点契约

**Files:**
- Create: `relief_story_agent/provider_catalog.py`
- Modify: `relief_story_agent/models.py`
- Modify: `relief_story_agent/pipeline.py`
- Test: `relief_story_agent/tests/test_provider_catalog.py`
- Test: `relief_story_agent/tests/test_pipeline_schema.py`

- [ ] **Step 1: 写失败测试**，断言 `quality_gate` 进入 `MODEL_STAGE_IDS`，国内/国际模型按设计规格隔离，未知站点和跨站模型被拒绝。
- [ ] **Step 2: 运行** `python -m pytest -q relief_story_agent/tests/test_provider_catalog.py relief_story_agent/tests/test_pipeline_schema.py`，预期因 catalog 不存在且 quality gate 非模型阶段失败。
- [ ] **Step 3: 实现** `ProviderMode`, `RunningHubSite`, `StageProviderBinding` 与 `get_curated_models(site, stage)`；把 `quality_gate` category 改为 `model`，保留本地规则输出。
- [ ] **Step 4: 再运行同一测试**，预期通过。
- [ ] **Step 5: 提交** `feat(core): define six-stage provider catalog`。

### Task 2: Prompt Profile HTTP API

**Files:**
- Modify: `relief_story_agent/prompt_profiles.py`
- Modify: `relief_story_agent/api.py`
- Modify: `relief_story_agent/orchestrator.py`
- Test: `relief_story_agent/tests/test_prompt_profiles.py`
- Test: `relief_story_agent/tests/test_api.py`

- [ ] **Step 1: 写失败测试**，覆盖 list/get/create/update/clone/delete/reset；系统默认不可删除和不可覆盖；更新必须递增 version 和 hash。
- [ ] **Step 2: 运行** `python -m pytest -q relief_story_agent/tests/test_prompt_profiles.py relief_story_agent/tests/test_api.py -k prompt_profile`，预期 API 404 或路由缺失。
- [ ] **Step 3: 实现** `/api/prompt-profiles` CRUD、`/{id}/clone`、`/{id}/reset`；错误返回稳定 `code/message/action`，API 不接收文件路径模板。
- [ ] **Step 4: 让 orchestrator 在创建 run 时解析并冻结 profile snapshot**，后续 profile 更新不得影响已创建 run。
- [ ] **Step 5: 再运行测试**，预期通过。
- [ ] **Step 6: 提交** `feat(api): expose versioned prompt profiles`。

### Task 3: 第三步 LLM 质量门禁

**Files:**
- Modify: `relief_story_agent/content.py`
- Modify: `relief_story_agent/orchestrator.py`
- Modify: `relief_story_agent/models.py`
- Test: `relief_story_agent/tests/test_prompt_workflow.py`
- Test: `relief_story_agent/tests/test_orchestrator.py`

- [ ] **Step 1: 写失败测试**，要求第 3 步调用配置模型并返回 `passed/issues/revision_instructions`；本地硬规则失败时即使 LLM 通过也必须失败。
- [ ] **Step 2: 运行目标测试**，预期当前 `_run_quality_gate` 不调用模型而失败。
- [ ] **Step 3: 新增 `build_quality_gate_prompt` 与结构化响应校验**，模板来自 `prompt_snapshot['quality_gate']`。
- [ ] **Step 4: 合并 LLM 报告和 `QualityGate.check_script_object`**，记录两份证据；硬规则拥有否决权。
- [ ] **Step 5: 运行** `python -m pytest -q relief_story_agent/tests/test_prompt_workflow.py relief_story_agent/tests/test_orchestrator.py`，预期通过。
- [ ] **Step 6: 提交** `feat(pipeline): add model-assisted script quality gate`。

### Task 4: RunningHub convenience LLM provider

**Files:**
- Create: `relief_story_agent/runninghub_llm.py`
- Modify: `relief_story_agent/providers.py`
- Modify: `relief_story_agent/model_runtime.py`
- Test: `relief_story_agent/tests/test_runninghub_llm.py`
- Test: `relief_story_agent/tests/test_model_runtime.py`

- [ ] **Step 1: 写失败测试**，覆盖 `.cn`/`.ai` base URL、Bearer key、chat completion 请求、JSON fenced 响应、429/5xx 重试和站点模型校验。
- [ ] **Step 2: 运行目标测试**，预期模块缺失。
- [ ] **Step 3: 实现 provider**，复用现有 OpenAI-compatible transport，但把站点、catalog 校验和错误归一化放在 `RunningHubLLMProvider`。
- [ ] **Step 4: 在 `ModelExecutor` 中按 `provider_mode` 路由**，普通兼容模式保持不变。
- [ ] **Step 5: 运行目标测试**，预期通过。
- [ ] **Step 6: 提交** `feat(models): add runninghub convenience llm routing`。

### Task 5: RunningHub G2 任务式生图

**Files:**
- Create: `relief_story_agent/runninghub_image.py`
- Modify: `relief_story_agent/models.py`
- Modify: `relief_story_agent/image_providers.py`
- Modify: `relief_story_agent/grid_image.py`
- Test: `relief_story_agent/tests/test_runninghub_image.py`
- Test: `relief_story_agent/tests/test_grid_image.py`

- [ ] **Step 1: 写失败测试**，覆盖创建 `rhart-image-g-2/text-to-image`、轮询 `/openapi/v2/query`、下载结果、默认 2K、16:9/9:16 和超时诊断。
- [ ] **Step 2: 写失败测试**，要求图像验证器按配置比例校验，不再固定要求近似正方形。
- [ ] **Step 3: 实现 `RunningHubImageTaskProvider`**，使用同站点密钥；响应解析允许平台返回的已知 URL 字段变体并保存原始 task id。
- [ ] **Step 4: 扩展 `GridImageConfig` 与 `validate_grid_image(expected_aspect_ratio=...)`**，四宫格仍要求四象限有像素变化。
- [ ] **Step 5: 运行** `python -m pytest -q relief_story_agent/tests/test_runninghub_image.py relief_story_agent/tests/test_grid_image.py relief_story_agent/tests/test_image_provider.py`，预期通过。
- [ ] **Step 6: 提交** `feat(images): add runninghub g2 task provider`。

### Task 6: RunRequest V2 完整快照与预检

**Files:**
- Modify: `relief_story_agent/models.py`
- Modify: `relief_story_agent/config_validation.py`
- Modify: `relief_story_agent/orchestrator.py`
- Test: `relief_story_agent/tests/test_v2_contract.py`
- Test: `relief_story_agent/tests/test_config_validation.py`

- [ ] **Step 1: 写失败测试**，覆盖空白 auto 输入、六阶段 binding、Prompt Profile、2K/比例、ComfyUI/workflow 和 batch defaults。
- [ ] **Step 2: 运行目标测试**，记录当前丢失字段。
- [ ] **Step 3: 完善 Pydantic 模型与 V1 迁移**，拒绝未知 stage，允许 auto 空内容，禁止序列化明文 key。
- [ ] **Step 4: 让预检返回用户级 `ready/blockers/warnings/actions` 与可选 `diagnostics`**，`passed` 与 `ready` 使用单一语义。
- [ ] **Step 5: 运行目标测试**，预期通过。
- [ ] **Step 6: 提交** `feat(api): complete autopilot run request snapshot`。

### Task 7: 增量事件和完整后端回归

**Files:**
- Modify: `relief_story_agent/api.py`
- Modify: `relief_story_agent/run_timeline.py`
- Test: `relief_story_agent/tests/test_run_events.py`
- Test: `relief_story_agent/tests/test_api.py`

- [ ] **Step 1: 写失败测试**，要求 `/events?after=<cursor>` 不重复返回并给出 `next_cursor`，run 详情含真实 current/last/failed stage。
- [ ] **Step 2: 实现游标响应并保持无参数旧响应兼容**。
- [ ] **Step 3: 运行** `python -m pytest -q relief_story_agent/tests/test_run_events.py relief_story_agent/tests/test_api.py`，预期通过。
- [ ] **Step 4: 运行全量** `python -m pytest -q relief_story_agent/tests`，预期 0 failures。
- [ ] **Step 5: 提交** `feat(api): add resumable run event cursor`。

