import { describe, expect, it } from 'vitest'
import { AUTOPILOT_STAGES, stageStatusFromTimeline } from './stages'

describe('ten-stage workbench contract', () => {
  it('keeps the cooking labels aligned with backend stage ids', () => {
    expect(AUTOPILOT_STAGES.map((stage) => stage.label)).toEqual([
      '备料', '慢炖', '试味', '配菜', '调味', '回锅', '锁菜谱', '出盘', '打包', '出餐中',
    ])
    expect(AUTOPILOT_STAGES[2].id).toBe('quality_gate')
    expect(AUTOPILOT_STAGES[9].id).toBe('comfyui')
  })

  it('marks the conditional reviser skipped after later stages complete', () => {
    expect(
      stageStatusFromTimeline('gpt_prompt_reviser', [], 'completed', 'final_prompts'),
    ).toBe('skipped')
  })
})

