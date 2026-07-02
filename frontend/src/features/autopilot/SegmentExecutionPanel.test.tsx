import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SegmentExecutionPanel } from './SegmentExecutionPanel'
import type { RenderPlan, SegmentRenderState } from '../workbench/workbench.api'

function segment(order: number): SegmentRenderState {
  return {
    segment_id: `segment-${order}`,
    shot_id: String(order),
    order,
    authored_time_range: `${(order - 1) * 20}-${order * 20}s`,
    render_time_range: `${(order - 1) * 20}-${order * 20}s`,
    duration_seconds: 20,
    fps: 24,
    frame_count: 480,
    local_frame_indices: [0, 160, 319, 479],
    positive_prompt: `camera prompt ${order}`,
    negative_prompt: 'watermark',
    seed: 3000 + order,
    strength: 0.76,
    grid_panel_prompts: ['wide', 'medium', 'close', 'reaction'],
    grid_image_prompt: `grid prompt ${order}`,
    workflow_name: 'LTX 2.3 production',
    workflow_path: 'D:/workflows/ltx.json',
    workflow_sha256: 'f'.repeat(64),
    workflow_api_artifact: `D:/runs/segment-${order}/workflow_api.json`,
    workflow_models: [{ node_id: '151', class_type: 'CheckpointLoaderSimple', title: 'LTX loader', input_name: 'ckpt_name', selected: 'ltx-2.3-22b.safetensors', available: true, choices: [] }],
    submission: { prompt_id: `prompt-${order}`, client_id: `client-${order}`, status: 'accepted' },
    outputs: [],
    status: order === 3 ? 'failed' : 'completed',
    error: order === 3 ? 'render failed' : '',
  }
}

describe('SegmentExecutionPanel', () => {
  it('shows exact segment execution details and recovery actions', () => {
    const plan: RenderPlan = {
      run_id: 'run-one', status: 'failed', current_stage: 'comfyui', duration_mode: 'auto',
      target_duration_seconds: 0, planned_duration_seconds: 120,
      segments: Array.from({ length: 6 }, (_, index) => segment(index + 1)),
      video_assembly: { status: 'pending', clip_paths: [], output_path: '', error: '' },
    }
    const retryVideo = vi.fn()
    render(<SegmentExecutionPanel plan={plan} onRetryImage={vi.fn()} onRetryVideo={retryVideo} onCancel={vi.fn()} />)

    expect(screen.getAllByRole('button', { name: /分段/ })).toHaveLength(6)
    fireEvent.click(screen.getByRole('button', { name: /分段 3/ }))

    expect(screen.getByText('20 秒')).toBeInTheDocument()
    expect(screen.getByText('24 FPS')).toBeInTheDocument()
    expect(screen.getByText('480 帧')).toBeInTheDocument()
    expect(screen.getByText('0, 160, 319, 479')).toBeInTheDocument()
    expect(screen.getByText('ltx-2.3-22b.safetensors')).toBeInTheDocument()
    expect(screen.getByText('prompt-3')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重试本段视频' }))
    expect(retryVideo).toHaveBeenCalledWith('segment-3')
  })
})
