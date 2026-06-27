# RunningHub Cloud Generation Mode 2 Design

## Context

Relief Story Agent already has a local ComfyUI generation path. That path stays
the release gate for local acceptance: real model probes, real local LTX 2.3
video output, batch evidence, restart recovery, export validation, and
`ready_for_release=true` are still required before calling the local backend
complete.

RunningHub is a second generation backend for users who want cloud GPU
execution. The user explicitly prefers the RunningHub advanced workflow API
where they upload or copy a `workflowId`; Relief Story Agent should not upload
the local ComfyUI JSON as the primary cloud contract.

Official RunningHub docs referenced on 2026-06-27:

- `https://www.runninghub.ai/runninghub-api-doc-en/doc-8287463`
- `https://www.runninghub.ai/runninghub-api-doc-en/api-425761093`

The advanced workflow start shape is `POST /task/openapi/create` with
`apiKey`, `workflowId`, and `nodeInfoList`. Status and outputs use
`/task/openapi/status` and `/task/openapi/outputs` with `apiKey` and `taskId`.

## Product Position

Generation mode 1 remains local ComfyUI. It is best for full local control,
workflow-file debugging, local output download, and current acceptance evidence.

Generation mode 2 is RunningHub cloud generation. It is best for cloud LTX 2.3
compute after the user has created or uploaded the workflow in RunningHub and
knows the workflow's node field mapping.

The UI should present these as two explicit choices:

- `Local ComfyUI`: endpoint, workflow path, output folder, local readiness.
- `RunningHub Cloud`: `workflowId`, API key environment variable status,
  `nodeInfoList` mapping, submit, poll status, fetch outputs.

## Data Contract

The local API accepts snake_case JSON for UI friendliness and converts it to
RunningHub's camelCase payload:

```json
{
  "workflow_id": "2038860299301818369",
  "api_key_env": "RUNNINGHUB_API_KEY",
  "base_url": "https://www.runninghub.ai",
  "node_info_list": [
    {
      "node_id": "1",
      "field_name": "text",
      "field_value": "prompt or asset URL",
      "description": "main prompt"
    }
  ],
  "webhook_url": "",
  "use_personal_queue": false,
  "instance_type": ""
}
```

The outbound create payload is:

```json
{
  "apiKey": "<from env>",
  "workflowId": "2038860299301818369",
  "nodeInfoList": [
    {
      "nodeId": "1",
      "fieldName": "text",
      "fieldValue": "prompt or asset URL",
      "description": "main prompt"
    }
  ]
}
```

## Security Boundary

API keys are never committed, never written into generated examples, and never
returned in API/CLI responses. The default environment variable name is
`RUNNINGHUB_API_KEY`. Dry-run payloads redact the key as
`<redacted:RUNNINGHUB_API_KEY>`.

The current implementation supports an in-process explicit `api_key` field for
advanced callers, but that field is excluded from public model dumps and should
not be stored in config files.

## Backend Entry Points

Local API:

- `POST /api/runninghub/check`
- `POST /api/runninghub/submit?dry_run=true|false`
- `POST /api/runninghub/status`
- `POST /api/runninghub/outputs`

CLI:

- `relief-story-agent runninghub-check --request runninghub.json --pretty`
- `relief-story-agent runninghub-submit --request runninghub.json --dry-run`
- `relief-story-agent runninghub-status --task-id TASK_ID`
- `relief-story-agent runninghub-outputs --task-id TASK_ID`

Example request:

- `relief_story_agent/examples/runninghub_request.example.json`

## UI Entry Design

The first UI version should be a practical operations surface, not a marketing
page:

- Segmented generation mode selector: Local ComfyUI / RunningHub Cloud.
- RunningHub setup panel:
  - workflow id input.
  - API key env name input, default `RUNNINGHUB_API_KEY`.
  - status pill from `/api/runninghub/check`.
  - node mapping table with node id, field name, field value, description.
  - dry-run payload preview with key redacted.
- RunningHub run panel:
  - submit button.
  - task id display.
  - status polling.
  - output URL list and manual download handoff.

The UI must not ask the user to paste plaintext API keys into local files. If a
temporary key input is ever added, it must be session-only and still redacted in
logs and responses.

## Error Handling

`runninghub-check` blocks submission when the API key environment variable is
missing. Submit dry-run still returns a payload preview and explicit checks.
Live submit/status/output calls return structured JSON for HTTP or transport
failures instead of tracebacks.

RunningHub result URLs are treated as cloud artifacts until a separate download
and provenance step exists. They do not satisfy the current local ComfyUI video
container evidence gate.

## Acceptance

Current starter acceptance for mode 2 is code-level:

- payload builder matches RunningHub advanced workflow API shape.
- missing key is diagnosed without leaking secrets.
- dry-run submit returns redacted payload.
- live submit/status/outputs can be exercised with mocked HTTP.
- API and CLI expose the entry points.

Future real acceptance for mode 2 requires:

- a real RunningHub membership/API key.
- a real uploaded/copied workflow id.
- confirmed node mapping for prompt/image/seed/output fields.
- live submit returning a task id.
- status polling to `SUCCESS` or a documented terminal failure.
- outputs containing expected video file URLs.
- optional download/validation if these outputs are imported into local export.
