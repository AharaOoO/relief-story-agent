import { describe, expect, it } from 'vitest'
import {
  buildBatchRunRequest,
  buildSetupBundleRequest,
  buildWorkflowDiscoveryRequest,
  toBackendRunRequest,
} from './backendPayloads'

describe('backend payload builders', () => {
  it('converts UI run state into the backend RunRequest shape', () => {
    expect(
      toBackendRunRequest({
        idea: '  quiet rain at a bus stop  ',
        generation_mode: 'local_comfyui',
        approval_mode: 'auto_after_audit_pass',
        duration_seconds: 60,
        dry_run: true,
      }),
    ).toEqual({
      idea: 'quiet rain at a bus stop',
      approval_mode: 'auto',
      duration_seconds: 60,
    })
  })

  it('builds a batch request from non-empty idea lines', () => {
    expect(
      buildBatchRunRequest({
        ideasText: 'first idea\n\n  second idea  ',
        approvalMode: 'manual',
        durationSeconds: 45,
      }),
    ).toEqual({
      items: [
        {
          idea: 'first idea',
          approval_mode: 'manual',
          duration_seconds: 45,
        },
        {
          idea: 'second idea',
          approval_mode: 'manual',
          duration_seconds: 45,
        },
      ],
    })
  })

  it('builds local setup bundle payload without secret values', () => {
    expect(
      buildSetupBundleRequest({
        outputDir: 'D:/relief_story_setup',
        workflowPath: 'D:/ComfyUI/workflows/story.json',
        comfyuiEndpoint: 'http://127.0.0.1:8188',
      }),
    ).toMatchObject({
      output_dir: 'D:/relief_story_setup',
      workflow_path: 'D:/ComfyUI/workflows/story.json',
      comfyui_endpoint: 'http://127.0.0.1:8188',
      gemini_api_key_env: 'GEMINI_API_KEY',
      deepseek_api_key_env: 'DEEPSEEK_API_KEY',
      gpt_api_key_env: 'OPENAI_API_KEY',
    })
  })

  it('builds ComfyUI workflow discovery payload from endpoint and roots', () => {
    expect(
      buildWorkflowDiscoveryRequest({
        endpoint: 'http://127.0.0.1:8188',
        searchRootsText: 'D:/ComfyUI/workflows\nD:/more',
      }),
    ).toEqual({
      endpoint: 'http://127.0.0.1:8188',
      search_roots: ['D:/ComfyUI/workflows', 'D:/more'],
      max_results: 25,
      include_unsupported: true,
      filename_keywords: ['ltx', 'story', 'workflow', 'four'],
    })
  })
})
