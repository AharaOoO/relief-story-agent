# Relief Story Agent Acceptance Report

Use this template for real local acceptance only. Do not mark a row complete until
the referenced artifact exists on the machine that ran the check.

| Check | Required Evidence | Status |
| --- | --- | --- |
| Full tests | `python -m pytest relief_story_agent/tests -q` output | |
| Local demo | `local_demo_summary.json`, fake model run artifacts, fake model batch summary, restart recovery drill | |
| ComfyUI dry smoke | `smoke_result.json`, no prompt id | |
| ComfyUI real smoke | `smoke_result.json`, prompt id | |
| Model check | `model-check` JSON, `ready=true` | |
| Run diagnose | `diagnose` run JSON, `ready=true` | |
| Batch diagnose | `diagnose --kind batch` JSON, `ready=true` | |
| Single run | run artifact dir, downloaded video path | |
| Batch run | batch id, item summaries | |
| Restart recovery | recovery-plan before/after restart | |
| Export | publish index, zip, sha256 | |
| Fresh setup | commands from docs run on clean env | |

Suggested generated report command:

```powershell
relief-story-agent local-acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --repo-root "D:/codex工作区" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --batch-request "D:/relief_story_config/batch_request.full-ltx.json" `
  --local-demo `
  --pretty
```

Manual report command:

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "local_e2e" `
  --status "manual_pending" `
  --check "full_tests=pass:238 passed" `
  --check "comfyui_real_smoke=manual_pending:" `
  --include-default-matrix `
  --notes "Record exact run ids, batch ids, artifact dirs, and video paths here."
```

The command writes `acceptance_report.json` and `ACCEPTANCE_REPORT.md`. Attach
the generated files with the referenced smoke, run, batch, export, and recovery
artifacts when handing the project to another reviewer.
