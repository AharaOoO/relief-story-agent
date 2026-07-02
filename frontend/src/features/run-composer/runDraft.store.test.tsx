import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useRunDraft } from './runDraft.store'

function DraftEditor() {
  const { patchDraft } = useRunDraft()
  return <button type="button" onClick={() => patchDraft({ content: '共享后的故事设定' })}>更新草稿</button>
}

function DraftPreview() {
  const { draft } = useRunDraft()
  return <output>{draft.content || '空草稿'}</output>
}

describe('run draft store', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('shares one draft between the stage editor and run composer', () => {
    render(<><DraftEditor /><DraftPreview /></>)

    act(() => screen.getByRole('button', { name: '更新草稿' }).click())

    expect(screen.getByText('共享后的故事设定')).toBeInTheDocument()
  })
})
