import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, Search } from 'lucide-react'

type ModelComboboxProps = {
  label: string
  value: string
  models: readonly string[]
  recommended?: readonly string[]
  disabled?: boolean
  onChange: (model: string) => void
}

function providerLabel(model: string) {
  const provider = model.includes('/') ? model.split('/')[0] : model.split('-')[0]
  const labels: Record<string, string> = {
    anthropic: 'Anthropic',
    bytedance: 'ByteDance',
    deepseek: 'DeepSeek',
    glm: '智谱 GLM',
    google: 'Google',
    minimax: 'MiniMax',
    openai: 'OpenAI',
    qwen: '阿里 Qwen',
    xai: 'xAI',
  }
  return labels[provider] ?? provider
}

export function ModelCombobox({
  label,
  value,
  models,
  recommended = [],
  disabled = false,
  onChange,
}: ModelComboboxProps) {
  const id = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)

  const normalizedModels = useMemo(
    () => Array.from(new Set(models.filter(Boolean))),
    [models],
  )
  const recommendedSet = useMemo(
    () => new Set(recommended.filter((model) => normalizedModels.includes(model))),
    [normalizedModels, recommended],
  )
  const visibleModels = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const matches = (model: string) => !needle || model.toLowerCase().includes(needle)
    return [
      ...recommended.filter((model) => recommendedSet.has(model) && matches(model)),
      ...normalizedModels.filter((model) => !recommendedSet.has(model) && matches(model)),
    ]
  }, [normalizedModels, query, recommended, recommendedSet])
  const recommendedModels = visibleModels.filter((model) => recommendedSet.has(model))
  const providerGroups = useMemo(() => {
    const groups = new Map<string, string[]>()
    for (const model of visibleModels) {
      if (recommendedSet.has(model)) continue
      const label = providerLabel(model)
      groups.set(label, [...(groups.get(label) ?? []), model])
    }
    return Array.from(groups.entries())
  }, [recommendedSet, visibleModels])

  useEffect(() => {
    if (!open) return
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    return () => document.removeEventListener('mousedown', closeOnOutsideClick)
  }, [open])

  useEffect(() => {
    if (!open) return
    setActiveIndex(0)
    queueMicrotask(() => searchRef.current?.focus())
  }, [open, query])

  const openPicker = () => {
    if (disabled) return
    setQuery('')
    setOpen(true)
  }

  const selectModel = (model: string) => {
    onChange(model)
    setOpen(false)
    setQuery('')
  }

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (disabled) return
    if (!open && ['ArrowDown', 'Enter', ' '].includes(event.key)) {
      event.preventDefault()
      openPicker()
      return
    }
    if (!open) return
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((current) => Math.min(current + 1, visibleModels.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((current) => Math.max(current - 1, 0))
    } else if (event.key === 'Enter' && visibleModels[activeIndex]) {
      event.preventDefault()
      selectModel(visibleModels[activeIndex])
    }
  }

  const renderOption = (model: string) => {
    const index = visibleModels.indexOf(model)
    return (
      <button
        id={`${id}-option-${index}`}
        key={model}
        type="button"
        role="option"
        aria-selected={model === value}
        className={`model-combobox-option ${index === activeIndex ? 'is-active' : ''}`}
        onMouseEnter={() => setActiveIndex(index)}
        onClick={() => selectModel(model)}
      >
        <span>{model}</span>
        {model === value && <Check size={15} aria-hidden="true" />}
      </button>
    )
  }

  return (
    <div className="field-stack model-combobox-field" ref={rootRef}>
      <span>{label}</span>
      <button
        type="button"
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={`${id}-listbox`}
        aria-activedescendant={open && visibleModels[activeIndex] ? `${id}-option-${activeIndex}` : undefined}
        className="model-combobox-trigger"
        disabled={disabled}
        onClick={() => open ? setOpen(false) : openPicker()}
        onKeyDown={handleKeyDown}
      >
        <span>{value || '选择模型'}</span>
        <ChevronDown size={17} aria-hidden="true" />
      </button>
      {open && (
        <div className="model-combobox-popover">
          <label className="model-combobox-search">
            <Search size={16} aria-hidden="true" />
            <input
              ref={searchRef}
              type="search"
              role="searchbox"
              aria-label="搜索模型"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="搜索模型名称"
            />
          </label>
          <div id={`${id}-listbox`} className="model-combobox-list" role="listbox" aria-label={`${label}选项`}>
            {recommendedModels.length > 0 && (
              <section className="model-combobox-group">
                <div className="model-combobox-group-title">推荐</div>
                {recommendedModels.map(renderOption)}
              </section>
            )}
            {providerGroups.map(([provider, providerModels]) => (
              <section className="model-combobox-group" key={provider}>
                <div className="model-combobox-group-title">{provider}</div>
                {providerModels.map(renderOption)}
              </section>
            ))}
            {visibleModels.length === 0 && <div className="model-combobox-empty">没有匹配的模型</div>}
          </div>
        </div>
      )}
    </div>
  )
}
