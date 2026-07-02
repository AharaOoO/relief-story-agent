import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ModelCombobox } from './ModelCombobox'

const models = [
  'google/gemini-3.5-flash',
  'openai/gpt-5.5',
  'anthropic/claude-sonnet-5',
  'deepseek/deepseek-v4-pro',
]

describe('ModelCombobox', () => {
  it('searches the complete catalog and selects a matching model', () => {
    const onChange = vi.fn()
    render(<ModelCombobox label="本工序模型" value="google/gemini-3.5-flash" models={models} recommended={models.slice(0, 2)} onChange={onChange} />)

    fireEvent.click(screen.getByRole('combobox', { name: '本工序模型' }))
    fireEvent.change(screen.getByRole('searchbox', { name: '搜索模型' }), { target: { value: 'sonnet-5' } })
    fireEvent.click(screen.getByRole('option', { name: 'anthropic/claude-sonnet-5' }))

    expect(onChange).toHaveBeenCalledWith('anthropic/claude-sonnet-5')
    expect(screen.getByRole('combobox', { name: '本工序模型' })).toHaveAttribute('aria-expanded', 'false')
  })

  it('puts recommendations before provider groups without duplicating options', () => {
    render(<ModelCombobox label="本工序模型" value="openai/gpt-5.5" models={models} recommended={['openai/gpt-5.5', 'google/gemini-3.5-flash']} onChange={() => undefined} />)

    fireEvent.click(screen.getByRole('combobox', { name: '本工序模型' }))
    const listbox = screen.getByRole('listbox', { name: '本工序模型选项' })
    const options = within(listbox).getAllByRole('option')

    expect(options.map((option) => option.textContent)).toEqual([
      'openai/gpt-5.5',
      'google/gemini-3.5-flash',
      'anthropic/claude-sonnet-5',
      'deepseek/deepseek-v4-pro',
    ])
    expect(within(listbox).getByText('推荐')).toBeInTheDocument()
    expect(within(listbox).getByText('Anthropic')).toBeInTheDocument()
  })

  it('supports arrow-key selection', () => {
    const onChange = vi.fn()
    render(<ModelCombobox label="本工序模型" value="google/gemini-3.5-flash" models={models} recommended={[]} onChange={onChange} />)

    const trigger = screen.getByRole('combobox', { name: '本工序模型' })
    fireEvent.keyDown(trigger, { key: 'ArrowDown' })
    const search = screen.getByRole('searchbox', { name: '搜索模型' })
    fireEvent.keyDown(search, { key: 'ArrowDown' })
    fireEvent.keyDown(search, { key: 'Enter' })

    expect(onChange).toHaveBeenCalledWith('openai/gpt-5.5')
  })

  it('stays closed and inert when disabled', () => {
    const onChange = vi.fn()
    render(<ModelCombobox label="本工序模型" value="glm-5.2" models={['glm-5.2']} recommended={['glm-5.2']} onChange={onChange} disabled />)

    const trigger = screen.getByRole('combobox', { name: '本工序模型' })
    fireEvent.click(trigger)

    expect(trigger).toBeDisabled()
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
  })
})
