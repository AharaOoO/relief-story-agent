# Prompt Template Guide

Prompt templates let operators iterate writer and audit behavior without code
changes. The pipeline order stays fixed:

```text
chief_screenwriter
-> deepseek_polish
-> quality_gate
-> gpt_prompt_writer
-> gpt_prompt_audit
-> gpt_prompt_reviser
-> final_prompts
-> four_grid_asset
-> artifacts
-> comfyui
```

`gpt_prompt_reviser` runs at most one revision after audit feedback. Do not turn
this into an unbounded loop; repeated failures should become a visible operator
review problem.

## Template Files

Setup writes editable templates to:

```text
D:/relief_story_config/templates/prompt_writer.default.md
D:/relief_story_config/templates/prompt_audit.default.md
```

Repository examples live at:

```text
relief_story_agent/examples/templates/prompt_writer.default.md
relief_story_agent/examples/templates/prompt_audit.default.md
```

## Supported Placeholders

Writer template:

- `{{script_json}}` is required.
- `{{duration_seconds}}` is optional.
- `{{preferred_style}}` is optional.
- `{{workflow_context}}` is optional.

Audit template:

- `{{script_json}}` is required.
- `{{storyboard_json}}` is required.
- `{{duration_seconds}}` is optional.
- `{{preferred_style}}` is optional.
- `{{workflow_context}}` is optional.

Reviser prompt is built in code and receives `{{audit_json}}` internally.

Unsupported placeholders fail validation so broken templates are caught before a
real run spends model quota.

## Writer Template Responsibilities

The writer should produce 5-8 shots with:

- `shot_id`
- `time_range`
- `description`
- `image_prompt`
- `negative_prompt`
- `scores`
- `comfyui_inputs`

Keep the `image_prompt` concise and concrete. For GPT image and LTX four-grid
keyframes, a prompt that clearly states character position, spatial relation,
lighting, emotion, and action is more useful than a long decorative paragraph.

## Audit Template Responsibilities

The audit should check:

- character count and position continuity;
- left/right and axis continuity;
- spatial relation clarity;
- motion logic between adjacent shots;
- static frame consistency for props, light, emotion, and setting;
- story meaning for every shot;
- prompt concision for four-grid keyframes.

The audit returns:

```json
{
  "passed": false,
  "issues": [
    {"code": "spatial_confusion", "message": "...", "shot_id": 1}
  ],
  "revision_instructions": ["..."],
  "scores": {}
}
```

When `passed=false`, the system calls `gpt_prompt_reviser` for one revision.

## Iteration Workflow

1. Edit one template change at a time.
2. Run:

```powershell
relief-story-agent template-check `
  --writer-template "D:/relief_story_config/templates/prompt_writer.default.md" `
  --audit-template "D:/relief_story_config/templates/prompt_audit.default.md" `
  --pretty

relief-story-agent diagnose `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --pretty
```

3. Run one single story with `preflight=true`.
4. Inspect artifacts:

```text
01_script.json
02_storyboard.json
04_prompt_audit.json
05_final_prompts.json
09_four_grid_prompt.json
```

5. If the template improves results, run a small batch.
6. Export and keep the template files with the acceptance report.

## Common Template Failures

Missing required placeholder:

- add `{{script_json}}` to writer templates;
- add both `{{script_json}}` and `{{storyboard_json}}` to audit templates.

Unsupported placeholder:

- use only the supported placeholder names;
- avoid spelling variants like `{{script}}` or `{{shots_json}}`.

Overlong image prompt:

- move story explanation into `description`;
- keep `image_prompt` focused on what the image/video model needs to see.

Audit too strict:

- make the audit report actionable issues;
- avoid rejecting every stylistic variation;
- keep one revision as the limit.

## Acceptance Evidence

Template changes are accepted only after artifacts show improved final prompts
and after the batch export still validates. Record the exact template paths and
sha256 provenance from diagnostics in the acceptance report.
