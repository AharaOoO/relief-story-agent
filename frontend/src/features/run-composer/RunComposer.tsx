import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  CheckCircle2,
  ChevronDown,
  FileInput,
  LoaderCircle,
  Minus,
  Play,
  Plus,
  SlidersHorizontal,
  Sparkles,
  XCircle,
} from 'lucide-react'
import {
  buildBatchRequest,
  buildRunRequest,
  createRunningHubStageModels,
  type RunDraft,
} from './runRequest.builder'
import { useRunDraft } from './runDraft.store'
import { createBatch, createRun, formatPreflightIssue, validateRun, type PreflightIssue, type PreflightResult } from '../workbench/workbench.api'

type RunComposerProps = {
  compact?: boolean
  heading?: string
  onDraftChange?: (draft: RunDraft) => void
}

const INPUT_MODES: Array<{ id: RunDraft['inputMode']; label: string; placeholder: string }> = [
  { id: 'auto', label: '自由创作', placeholder: '不写也可以，AI 会从零确定故事内核；也可以输入一句灵感或大致方向。' },
  { id: 'idea', label: '一句灵感', placeholder: '例如：一个深夜下班的人，在便利店门口被一杯热饮安慰。' },
  { id: 'requirements', label: '创作要求', placeholder: '写下题材、受众、核心矛盾、禁忌或必须保留的设定。' },
  { id: 'script', label: '已有剧本', placeholder: '粘贴现有剧本，流水线会在保留原剧情的前提下完成影视化改稿。' },
  { id: 'mixed', label: '剧本 + 要求', placeholder: '粘贴剧本，并在末尾补充改编要求与必须保留的内容。' },
]

function inferInputMode(content: string): RunDraft['inputMode'] {
  const text = content.trim()
  if (!text) return 'auto'

  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  const hasRequirementSignal = /要求|目标|受众|风格|限制|必须|不要|需要|参考|核心|主题|画面风格|创作/.test(text)
  const hasSceneHeading = /第\s*[一二三四五六七八九十\d]+\s*[场幕]/.test(text)
  const hasLocationTime = /(?:内|外)\s*(?:日|夜)|INT\.|EXT\./i.test(text)
  const hasDialogueLine = /^\s*[\u4e00-\u9fa5A-Za-z0-9_]{1,12}[：:]/m.test(text)
  const hasShotLanguage = /镜头|对白|旁白|画面|CUT TO/i.test(text)
  const looksLikeScript = (
    hasSceneHeading ||
    hasLocationTime ||
    ((hasDialogueLine || hasShotLanguage) && lines.length >= 3) ||
    (lines.length >= 4 && text.length > 200)
  )

  if (looksLikeScript && hasRequirementSignal) return 'mixed'
  if (looksLikeScript) return 'script'
  if (hasRequirementSignal) return 'requirements'
  if (text.length <= 160 && lines.length <= 2) return 'idea'
  return 'requirements'
}

function isPreflightReady(result: PreflightResult | null) {
  if (!result) return false
  return result.ready ?? result.passed ?? false
}

type PreflightCheck = NonNullable<PreflightResult['checks']>[number]
type SuggestedAction = NonNullable<PreflightResult['suggested_actions']>[number]

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : null
}

function findPreflightValidation(caught: unknown): PreflightResult | null {
  const errorRecord = asRecord(caught)
  if (!errorRecord) return null
  const rawRecord = asRecord(errorRecord.raw)
  const validation = (
    (rawRecord ? validationFromRecord(rawRecord) : null) ??
    validationFromRecord(errorRecord)
  )
  return validation ? normalizePreflightValidation(validation) : null
}

function validationFromRecord(record: Record<string, unknown>): Record<string, unknown> | null {
  const direct = asRecord(record.validation)
  if (direct) return direct
  const detail = asRecord(record.detail)
  return detail ? asRecord(detail.validation) : null
}

function normalizePreflightValidation(validation: Record<string, unknown>): PreflightResult {
  const blockers = [
    ...extractIssueList(validation.blockers),
    ...extractBatchBlockers(validation.items),
  ]
  if (validation.passed !== true && blockers.length === 0) {
    blockers.push('配置预检未通过，请打开高级设置查看诊断。')
  }
  return {
    ready: typeof validation.ready === 'boolean' ? validation.ready : validation.passed === true,
    passed: validation.passed === true,
    blockers,
    warnings: extractIssueList(validation.warnings),
    suggested_actions: extractSuggestedActions(validation.suggested_actions),
    checks: extractChecks(validation.checks),
  }
}

function extractIssueList(value: unknown): PreflightIssue[] {
  return Array.isArray(value) ? value.filter(isPreflightIssue) : []
}

function isPreflightIssue(value: unknown): value is PreflightIssue {
  if (typeof value === 'string') return true
  const record = asRecord(value)
  return Boolean(record && (
    typeof record.message === 'string' ||
    typeof record.description === 'string' ||
    typeof record.check === 'string' ||
    typeof record.code === 'string'
  ))
}

function extractBatchBlockers(value: unknown): PreflightIssue[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item, fallbackIndex) => {
    const record = asRecord(item)
    if (!record || record.passed === true) return []
    const index = typeof record.index === 'number' ? record.index + 1 : fallbackIndex + 1
    const failedChecks = extractChecks(record.checks).filter((check) => check.status === 'failed')
    if (failedChecks.length === 0) return [`任务 ${index}：配置预检未通过。`]
    return failedChecks.map((check) => `任务 ${index}：${check.message || check.name}`)
  })
}

function extractChecks(value: unknown): PreflightCheck[] {
  return Array.isArray(value) ? value.filter(isPreflightCheck) : []
}

function isPreflightCheck(value: unknown): value is PreflightCheck {
  const record = asRecord(value)
  return Boolean(
    record &&
    typeof record.name === 'string' &&
    typeof record.status === 'string' &&
    typeof record.message === 'string',
  )
}

function extractSuggestedActions(value: unknown): SuggestedAction[] {
  return Array.isArray(value) ? value.filter(isSuggestedAction) : []
}

function isSuggestedAction(value: unknown): value is SuggestedAction {
  const record = asRecord(value)
  return Boolean(
    record &&
    typeof record.code === 'string' &&
    typeof record.label === 'string' &&
    (record.description === undefined || typeof record.description === 'string'),
  )
}

export function RunComposer({ compact = false, heading, onDraftChange }: RunComposerProps) {
  const navigate = useNavigate()
  const { draft, patchDraft } = useRunDraft()
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [preflight, setPreflight] = useState<PreflightResult | null>(null)
  const [feedback, setFeedback] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const manualModeRef = useRef(false)
  const inputMode = INPUT_MODES.find((item) => item.id === draft.inputMode) ?? INPUT_MODES[0]
  const preflightReady = isPreflightReady(preflight)

  useEffect(() => onDraftChange?.(draft), [draft, onDraftChange])

  useEffect(() => {
    const applyRuntime = (config: Record<string, unknown>) => {
      patchDraft({
        ...(typeof config.comfyui_endpoint === 'string' ? { comfyuiEndpoint: config.comfyui_endpoint } : {}),
        ...(typeof config.workflow_path === 'string' ? { workflowPath: config.workflow_path } : {}),
        ...(typeof config.output_root === 'string' ? { outputRoot: config.output_root } : {}),
      })
    }
    if (window.reliefDesktop) {
      void window.reliefDesktop.getRuntimeConfig().then(applyRuntime)
    }
    const listener = (event: Event) => applyRuntime((event as CustomEvent<Record<string, unknown>>).detail)
    window.addEventListener('relief:runtime-config', listener)
    return () => window.removeEventListener('relief:runtime-config', listener)
  }, [patchDraft])

  const mutation = useMutation({
    mutationFn: async (mode: 'preflight' | 'create') => {
      const request = buildRunRequest(draft)
      if (mode === 'preflight') return { kind: 'preflight' as const, value: await validateRun(request) }
      if (draft.taskCount > 1) return { kind: 'batch' as const, value: await createBatch(buildBatchRequest(draft)) }
      return { kind: 'run' as const, value: await createRun(request) }
    },
    onMutate: (mode) => {
      setPreflight(null)
      setFeedback(mode === 'preflight' ? '正在检查模型、工作流与 ComfyUI…' : draft.taskCount > 1 ? `正在创建 ${draft.taskCount} 个任务…` : '正在创建任务并启动十步流水线…')
    },
    onSuccess: (result) => {
      if (result.kind === 'preflight') {
        setPreflight(result.value)
        setFeedback(isPreflightReady(result.value) ? '预检通过，可以开始生成。' : '预检发现阻塞项，请按提示修正。')
        return
      }
      if (result.kind === 'batch') {
        setFeedback('批量任务已进入队列。')
        navigate('/tasks')
        return
      }
      setFeedback('任务已启动，正在进入第一道工序。')
      navigate(`/run/${result.value.run_id}`)
    },
    onError: (caught) => {
      const validation = findPreflightValidation(caught)
      if (validation) {
        setPreflight(validation)
        setFeedback(isPreflightReady(validation) ? '预检通过，可以开始生成。' : '预检发现阻塞项，请按提示修正。')
        return
      }
      const error: unknown = caught
      if (error instanceof Error) {
        setFeedback(error.message)
      } else if (typeof error === 'object' && error !== null && 'message' in error && typeof error.message === 'string') {
        setFeedback(error.message)
      } else {
        setFeedback('操作失败，请检查高级设置。')
      }
    },
  })

  const importScript = async () => {
    const picked = await window.reliefDesktop?.pickScript()
    if (!picked || picked.canceled || !picked.content) return
    manualModeRef.current = true
    patchDraft({ content: picked.content, sourceName: picked.name ?? '', inputMode: 'script' })
    setFeedback(`已导入 ${picked.name ?? '剧本文件'}。`)
    textareaRef.current?.focus()
  }

  const changeSite = (site: RunDraft['runninghubSite']) => {
    patchDraft({ runninghubSite: site, stageModels: createRunningHubStageModels(site) })
  }

  const updateInputMode = (mode: RunDraft['inputMode']) => {
    manualModeRef.current = mode !== 'auto'
    patchDraft({ inputMode: mode })
  }

  const updateContent = (content: string) => {
    patchDraft({
      content,
      ...(!manualModeRef.current ? { inputMode: inferInputMode(content) } : {}),
    })
  }

  return (
    <section className={compact ? 'run-composer is-compact' : 'run-composer'} aria-label="创作任务">
      {heading && <div className="composer-heading"><span className="eyebrow">NEW PRODUCTION</span><h2>{heading}</h2></div>}
      <div className="composer-mode-row">
        <label className="select-pill">
          <span className="sr-only">输入类型</span>
          <select value={draft.inputMode} onChange={(event) => updateInputMode(event.target.value as RunDraft['inputMode'])}>
            {INPUT_MODES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
          <ChevronDown size={15} />
        </label>
        <div className="mode-note">有剧本就优化，没有内容就自动创作。</div>
        <button className="text-button" type="button" onClick={() => void importScript()} disabled={!window.reliefDesktop}>
          <FileInput size={16} /> 导入剧本
        </button>
      </div>

      <textarea
        ref={textareaRef}
        value={draft.content}
        onChange={(event) => updateContent(event.target.value)}
        placeholder={inputMode.placeholder}
        aria-label="故事灵感、剧本或创作要求"
      />

      <div className="composer-controls">
        <label className="select-control">
          <span>时长</span>
          <select value={draft.durationSeconds} onChange={(event) => patchDraft({ durationSeconds: Number(event.target.value) })}>
            <option value={60}>约 1 分钟</option>
            <option value={90}>约 90 秒</option>
            <option value={180}>约 3 分钟</option>
            <option value={300}>约 5 分钟</option>
          </select>
        </label>

        <div className="segmented-control" aria-label="画面比例">
          <button type="button" className={draft.aspectRatio === '16:9' ? 'is-active' : ''} onClick={() => patchDraft({ aspectRatio: '16:9' })}>横屏 16:9</button>
          <button type="button" className={draft.aspectRatio === '9:16' ? 'is-active' : ''} onClick={() => patchDraft({ aspectRatio: '9:16' })}>竖屏 9:16</button>
        </div>

        <label className="select-control">
          <span>参考图</span>
          <select value={draft.imageResolution} onChange={(event) => patchDraft({ imageResolution: event.target.value as RunDraft['imageResolution'] })}>
            <option value="2k">2K 清晰</option>
            <option value="1k">1K 快速</option>
          </select>
        </label>

        <div className="stepper" aria-label="任务数量">
          <span>任务</span>
          <button type="button" onClick={() => patchDraft({ taskCount: Math.max(1, draft.taskCount - 1) })} aria-label="减少任务"><Minus size={14} /></button>
          <strong>{draft.taskCount}</strong>
          <button type="button" onClick={() => patchDraft({ taskCount: Math.min(20, draft.taskCount + 1) })} aria-label="增加任务"><Plus size={14} /></button>
        </div>

        <button className="secondary-button compact" type="button" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}>
          <SlidersHorizontal size={16} /> 创作参数
        </button>
      </div>

      {advancedOpen && (
        <div className="composer-advanced">
          <label className="field-stack"><span>系列名</span><input value={draft.seriesName} placeholder="例如：便利店夜话" onChange={(event) => patchDraft({ seriesName: event.target.value })} /></label>
          <label className="field-stack"><span>目标观众</span><input value={draft.audience} placeholder="例如：20-35 岁都市上班族" onChange={(event) => patchDraft({ audience: event.target.value })} /></label>
          <label className="field-stack"><span>画面风格</span><input value={draft.stylePresetId} placeholder="cinematic suspense" onChange={(event) => patchDraft({ stylePresetId: event.target.value })} /></label>
          <label className="field-stack span-all"><span>创作约束</span><textarea value={draft.creativeConstraints} placeholder="每行一条，例如：不使用旁白；角色不超过 3 人。" onChange={(event) => patchDraft({ creativeConstraints: event.target.value })} /></label>
          <div className="field-stack"><span>RunningHub 站点</span><div className="segmented-control"><button type="button" className={draft.runninghubSite === 'cn' ? 'is-active' : ''} onClick={() => changeSite('cn')}>国内站 .cn</button><button type="button" className={draft.runninghubSite === 'ai' ? 'is-active' : ''} onClick={() => changeSite('ai')}>国际站 .ai</button></div></div>
          <label className="field-stack"><span>审核方式</span><select value={draft.approvalMode} onChange={(event) => patchDraft({ approvalMode: event.target.value as RunDraft['approvalMode'] })}><option value="auto">自动执行到底</option><option value="manual">提示词后人工确认</option></select></label>
        </div>
      )}

      <footer className="composer-footer">
        <div className="composer-feedback" role="status">
          {mutation.isPending && <LoaderCircle className="spin" size={17} />}
          {!mutation.isPending && preflightReady && <CheckCircle2 size={17} />}
          {!mutation.isPending && preflight && !preflightReady && <XCircle size={17} />}
          <span>{feedback || `${draft.runninghubSite === 'cn' ? '国内站' : '国际站'} · ${draft.aspectRatio} · ${draft.imageResolution.toUpperCase()} · ${draft.taskCount} 个任务`}</span>
        </div>
        <div className="composer-actions">
          <button type="button" className="secondary-button" disabled={mutation.isPending} onClick={() => mutation.mutate('preflight')}>
            <Sparkles size={17} /> 预检
          </button>
          <button type="button" className="primary-button" disabled={mutation.isPending} onClick={() => mutation.mutate('create')}>
            {mutation.isPending ? <LoaderCircle className="spin" size={18} /> : <Play size={18} />}
            {draft.taskCount > 1 ? `批量开始 ${draft.taskCount} 个任务` : '一键开始生成'}
          </button>
        </div>
      </footer>

      {preflight && !preflightReady && (
        <div className="preflight-result is-error">
          <strong>还需要处理：</strong>
          <ul>{(preflight.blockers ?? []).map((item, index) => {
            const message = formatPreflightIssue(item)
            return <li key={`${message}-${index}`}>{message}</li>
          })}</ul>
        </div>
      )}
    </section>
  )
}
