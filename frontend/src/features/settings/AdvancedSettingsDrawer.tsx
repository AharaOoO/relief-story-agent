import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Check,
  ChevronRight,
  Eye,
  EyeOff,
  FileJson,
  FolderOpen,
  Image as ImageIcon,
  KeyRound,
  LoaderCircle,
  RefreshCw,
  ScrollText,
  ServerCog,
  X,
} from 'lucide-react'
import { useBackendHealth } from '../../shared/hooks/useBackendHealth'
import { applyDesktopHandshake } from '../../shared/api/desktopHandshake'
import {
  analyzeComfyWorkflow,
  connectComfyUI,
  diagnoseRunConfiguration,
  type RunConfigurationDiagnosis,
} from '../workbench/workbench.api'
import { buildRunRequest, createRunningHubStageModels } from '../run-composer/runRequest.builder'
import { useRunDraft } from '../run-composer/runDraft.store'
import { PromptProfileSettings } from './PromptProfileSettings'

type SettingsTab = 'secrets' | 'prompts' | 'comfyui' | 'image' | 'storage' | 'diagnostics'
type SecretStatus = Record<string, { configured: boolean; masked: string }>
type DesktopRuntimeHandshake = {
  backendUrl: string
  backendPort: number | null
  backendStatus: string
  backendLogPath: string
  backendLastError: string
  version: string
}
type RuntimeConfig = {
  comfyui_endpoint?: string
  workflow_path?: string
  output_root?: string
  gemini_base_url?: string
  gemini_model?: string
  deepseek_base_url?: string
  deepseek_model?: string
  openai_base_url?: string
  openai_model?: string
  max_workers?: number
  image_generation_concurrency?: number
  comfyui_submission_concurrency?: number
}

type AdvancedSettingsDrawerProps = {
  open: boolean
  onClose: () => void
}

const SECRET_FIELDS = [
  { name: 'RUNNINGHUB_CN_API_KEY', label: 'RunningHub 国内站', hint: '.cn 站 LLM 与 G2 共用' },
  { name: 'RUNNINGHUB_AI_API_KEY', label: 'RunningHub 国际站', hint: '.ai 站 LLM 与 G2 共用' },
  { name: 'GEMINI_API_KEY', label: 'Gemini', hint: '普通模型 API 模式' },
  { name: 'DEEPSEEK_API_KEY', label: 'DeepSeek', hint: '普通模型 API 模式' },
  { name: 'OPENAI_API_KEY', label: 'OpenAI / 图像', hint: '普通模型 API 模式' },
] as const

function isDesktop() {
  return typeof window !== 'undefined' && Boolean(window.reliefDesktop)
}

export function AdvancedSettingsDrawer({ open, onClose }: AdvancedSettingsDrawerProps) {
  const [tab, setTab] = useState<SettingsTab>('secrets')
  const [secretStatus, setSecretStatus] = useState<SecretStatus>({})
  const [secretValues, setSecretValues] = useState<Record<string, string>>({})
  const [visibleSecret, setVisibleSecret] = useState<string>('')
  const [runtime, setRuntime] = useState<RuntimeConfig>({
    comfyui_endpoint: 'http://127.0.0.1:8188',
    workflow_path: '',
    output_root: '',
    gemini_base_url: 'https://generativelanguage.googleapis.com/v1beta/openai',
    gemini_model: 'gemini-2.5-pro',
    deepseek_base_url: 'https://api.deepseek.com/v1',
    deepseek_model: 'deepseek-chat',
    openai_base_url: 'https://api.openai.com/v1',
    openai_model: 'gpt-5-mini',
  })
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [workflowReport, setWorkflowReport] = useState<Record<string, unknown> | null>(null)
  const [diagnosisReport, setDiagnosisReport] = useState<RunConfigurationDiagnosis | null>(null)
  const [handshake, setHandshake] = useState<DesktopRuntimeHandshake | null>(null)
  const drawerRef = useRef<HTMLElement>(null)
  const { draft: runDraft, patchDraft: patchRunDraft } = useRunDraft()
  const health = useBackendHealth()

  useEffect(() => {
    if (!open || !window.reliefDesktop) return
    setMessage('')
    void Promise.all([
      window.reliefDesktop.getRuntimeConfig(),
      window.reliefDesktop.getSecretStatus(),
      window.reliefDesktop.getHandshake(),
    ]).then(([savedRuntime, savedStatus, currentHandshake]) => {
      setRuntime((current) => ({ ...current, ...(savedRuntime as RuntimeConfig) }))
      setSecretStatus(savedStatus)
      setHandshake(currentHandshake)
    }).catch((error: unknown) => {
      setMessage(error instanceof Error ? error.message : '无法读取桌面设置')
    })
  }, [open])

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    window.setTimeout(() => drawerRef.current?.querySelector<HTMLElement>('[data-autofocus]')?.focus(), 0)
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key !== 'Tab' || !drawerRef.current) return
      const focusable = Array.from(drawerRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex="-1"])'))
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      window.removeEventListener('keydown', closeOnEscape)
      previouslyFocused?.focus()
    }
  }, [onClose, open])

  const configuredCount = useMemo(
    () => Object.values(secretStatus).filter((item) => item.configured).length,
    [secretStatus],
  )

  if (!open) return null

  const saveSecret = async (name: string) => {
    const value = secretValues[name]?.trim()
    if (!value || !window.reliefDesktop) return
    setBusy(name)
    setMessage('正在安全保存并重启本地后端…')
    try {
      const result = await window.reliefDesktop.saveSecret(name, value)
      applyDesktopHandshake(result.handshake)
      setSecretStatus((current) => ({
        ...current,
        [name]: result.status,
      }))
      setSecretValues((current) => ({ ...current, [name]: '' }))
      setMessage('API Key 已加密保存，本地后端已读取新配置。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'API Key 保存失败')
    } finally {
      setBusy('')
    }
  }

  const deleteSecret = async (name: string) => {
    if (!window.reliefDesktop) return
    setBusy(name)
    setMessage('正在移除密钥并重启本地后端…')
    try {
      const result = await window.reliefDesktop.deleteSecret(name)
      applyDesktopHandshake(result.handshake)
      setSecretStatus((current) => ({ ...current, [name]: result.status }))
      setMessage('密钥已从 Windows 加密存储中移除。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '密钥移除失败')
    } finally {
      setBusy('')
    }
  }

  const saveRuntime = async () => {
    if (!window.reliefDesktop) return
    setBusy('runtime')
    setMessage('正在保存配置并重启本地后端…')
    try {
      const result = await window.reliefDesktop.saveRuntimeConfig(runtime)
      applyDesktopHandshake(result.handshake)
      const config = result.config as RuntimeConfig
      setRuntime((current) => ({ ...current, ...config }))
      setHandshake(result.handshake)
      window.dispatchEvent(new CustomEvent('relief:runtime-config', { detail: config }))
      setMessage('本地配置已保存，后端已重新连接。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '本地配置保存失败')
    } finally {
      setBusy('')
    }
  }

  const pickWorkflow = async () => {
    const result = await window.reliefDesktop?.pickWorkflow()
    if (!result?.canceled && result?.path) {
      setRuntime((current) => ({ ...current, workflow_path: result.path }))
    }
  }

  const pickOutputRoot = async () => {
    const result = await window.reliefDesktop?.pickDirectory()
    if (!result?.canceled && result?.path) {
      setRuntime((current) => ({ ...current, output_root: result.path }))
    }
  }

  const verifyWorkflow = async () => {
    if (!window.reliefDesktop) return
    const endpoint = runtime.comfyui_endpoint?.trim() || 'http://127.0.0.1:8188'
    const workflowPath = runtime.workflow_path?.trim() || ''
    if (!workflowPath) {
      setMessage('请先选择或拖入 ComfyUI workflow JSON。')
      return
    }
    setBusy('workflow')
    setMessage('正在保存、分析工作流并测试 ComfyUI 连接…')
    setWorkflowReport(null)
    try {
      const saved = await window.reliefDesktop.saveRuntimeConfig(runtime)
      applyDesktopHandshake(saved.handshake)
      setRuntime((current) => ({ ...current, ...(saved.config as RuntimeConfig) }))
      setHandshake(saved.handshake)
      window.dispatchEvent(new CustomEvent('relief:runtime-config', { detail: saved.config }))
      const [analysis, connection] = await Promise.all([
        analyzeComfyWorkflow(endpoint, workflowPath),
        connectComfyUI(endpoint, workflowPath),
      ])
      const connected = Boolean(connection.connected)
      setWorkflowReport({ analysis, connection })
      setMessage(connected ? `工作流可用：${String(analysis.adapter_mode ?? analysis.workflow_format ?? '已识别')}，ComfyUI 已连接。` : '工作流已识别，但 ComfyUI 当前未连接。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '工作流分析或连接失败')
    } finally {
      setBusy('')
    }
  }

  const runDeepDiagnosis = async () => {
    setBusy('diagnosis')
    setMessage('正在运行深度配置诊断...')
    setDiagnosisReport(null)
    try {
      const result = await diagnoseRunConfiguration(buildRunRequest(runDraft))
      const failed = Number(result.summary?.failed ?? 0)
      setDiagnosisReport(result)
      setMessage(failed > 0 ? '深度诊断发现阻塞项，请查看下方结果。' : '深度诊断通过，当前配置可以继续执行。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '深度诊断失败')
    } finally {
      setBusy('')
    }
  }

  const tabs: Array<{ id: SettingsTab; label: string; icon: typeof KeyRound }> = [
    { id: 'secrets', label: '模型与密钥', icon: KeyRound },
    { id: 'prompts', label: '提示词模板', icon: ScrollText },
    { id: 'comfyui', label: 'ComfyUI', icon: ServerCog },
    { id: 'image', label: '图像生成', icon: ImageIcon },
    { id: 'storage', label: '执行与存储', icon: FolderOpen },
    { id: 'diagnostics', label: '诊断', icon: RefreshCw },
  ]

  const diagnosisSummary = diagnosisReport?.summary ?? {}
  const diagnosisPassed = Number(diagnosisSummary.passed ?? 0)
  const diagnosisWarnings = Number(diagnosisSummary.warning ?? diagnosisSummary.warnings ?? 0)
  const diagnosisFailed = Number(diagnosisSummary.failed ?? 0)
  const visibleDiagnosisChecks = diagnosisReport?.checks
    ?.filter((check) => check.status !== 'passed')
    .slice(0, 3) ?? []

  return (
    <div className="settings-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        ref={drawerRef}
        className="settings-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="高级设置"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="settings-header">
          <div>
            <span className="eyebrow">ADVANCED SETUP</span>
            <h2>高级设置</h2>
            <p>平时收起来，需要时再打开。</p>
          </div>
          <button className="icon-button" type="button" data-autofocus onClick={onClose} aria-label="关闭高级设置">
            <X size={20} />
          </button>
        </header>

        <div className="settings-layout">
          <div className="settings-tabs" role="tablist" aria-label="高级设置分组">
            {tabs.map((item) => {
              const Icon = item.icon
              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === item.id}
                  className={tab === item.id ? 'is-active' : ''}
                  onClick={() => setTab(item.id)}
                >
                  <Icon size={17} />
                  <span>{item.label}</span>
                  <ChevronRight size={15} />
                </button>
              )
            })}
          </div>

          <div className="settings-content">
            {!isDesktop() && (
              <div className="inline-notice is-warning">
                请从桌面客户端打开此页，浏览器预览不会保存本机密钥或路径。
              </div>
            )}

            {tab === 'secrets' && (
              <div className="settings-section">
                <div className="section-heading-row">
                  <div>
                    <h3>模型访问密钥</h3>
                    <p>{configuredCount} 项已配置。密钥只保存在 Windows 加密存储中。</p>
                  </div>
                </div>
                <div className="secret-list">
                  {SECRET_FIELDS.map((field) => {
                    const status = secretStatus[field.name]
                    return (
                      <div className="secret-row" key={field.name}>
                        <div className="secret-copy">
                          <strong>{field.label}</strong>
                          <span>{field.hint}</span>
                        </div>
                        <div className="secret-status">
                          {status?.configured ? <><Check size={14} /> {status.masked}</> : '未配置'}
                        </div>
                        <div className="secret-input-wrap">
                          <input
                            type={visibleSecret === field.name ? 'text' : 'password'}
                            value={secretValues[field.name] ?? ''}
                            onChange={(event) => setSecretValues((current) => ({ ...current, [field.name]: event.target.value }))}
                            placeholder={status?.configured ? '输入新 key 可替换' : '粘贴 API Key'}
                            autoComplete="off"
                          />
                          <button
                            className="icon-button is-quiet"
                            type="button"
                            onClick={() => setVisibleSecret((current) => current === field.name ? '' : field.name)}
                            aria-label={visibleSecret === field.name ? `隐藏 ${field.label} 密钥` : `显示 ${field.label} 密钥`}
                          >
                            {visibleSecret === field.name ? <EyeOff size={17} /> : <Eye size={17} />}
                          </button>
                        </div>
                        <div className="secret-button-row">
                          {status?.configured && <button className="text-button" type="button" disabled={Boolean(busy)} onClick={() => void deleteSecret(field.name)}>清除</button>}
                          <button
                            className="secondary-button compact"
                            type="button"
                            disabled={!secretValues[field.name]?.trim() || Boolean(busy)}
                            onClick={() => void saveSecret(field.name)}
                          >
                            {busy === field.name ? <LoaderCircle className="spin" size={16} /> : <KeyRound size={16} />}
                            保存
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
                <details className="endpoint-details">
                  <summary>普通模型 API 兼容端点</summary>
                  <p>只有使用中转站或自定义兼容服务时才需要修改。</p>
                  <div className="endpoint-grid">
                    <label className="field-stack"><span>Gemini BASE URL</span><input value={runtime.gemini_base_url ?? ''} onChange={(event) => setRuntime((current) => ({ ...current, gemini_base_url: event.target.value }))} /></label>
                    <label className="field-stack"><span>Gemini 模型</span><input value={runtime.gemini_model ?? ''} onChange={(event) => setRuntime((current) => ({ ...current, gemini_model: event.target.value }))} /></label>
                    <label className="field-stack"><span>DeepSeek BASE URL</span><input value={runtime.deepseek_base_url ?? ''} onChange={(event) => setRuntime((current) => ({ ...current, deepseek_base_url: event.target.value }))} /></label>
                    <label className="field-stack"><span>DeepSeek 模型</span><input value={runtime.deepseek_model ?? ''} onChange={(event) => setRuntime((current) => ({ ...current, deepseek_model: event.target.value }))} /></label>
                    <label className="field-stack"><span>OpenAI BASE URL</span><input value={runtime.openai_base_url ?? ''} onChange={(event) => setRuntime((current) => ({ ...current, openai_base_url: event.target.value }))} /></label>
                    <label className="field-stack"><span>OpenAI 模型</span><input value={runtime.openai_model ?? ''} onChange={(event) => setRuntime((current) => ({ ...current, openai_model: event.target.value }))} /></label>
                  </div>
                  <button className="secondary-button" type="button" disabled={Boolean(busy) || !isDesktop()} onClick={() => void saveRuntime()}>{busy === 'runtime' ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />} 保存兼容端点</button>
                </details>
              </div>
            )}

            {tab === 'prompts' && <PromptProfileSettings />}

            {tab === 'comfyui' && (
              <div className="settings-section">
                <div>
                  <h3>ComfyUI 与专属工作流</h3>
                  <p>桌面端会保存这些路径，并在每次任务中自动注入。</p>
                </div>
                <label className="field-stack">
                  <span>ComfyUI 地址</span>
                  <input value={runtime.comfyui_endpoint ?? ''} onChange={(event) => setRuntime((current) => ({ ...current, comfyui_endpoint: event.target.value }))} />
                </label>
                <label className="field-stack">
                  <span>工作流 JSON</span>
                  <div className="input-action-row">
                    <input value={runtime.workflow_path ?? ''} onChange={(event) => setRuntime((current) => ({ ...current, workflow_path: event.target.value }))} />
                    <button className="icon-button" type="button" onClick={() => void pickWorkflow()} aria-label="选择工作流文件">
                      <FileJson size={18} />
                    </button>
                  </div>
                </label>
                <div
                  className="file-drop-zone"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault()
                    const file = event.dataTransfer.files[0]
                    const droppedPath = file && window.reliefDesktop
                      ? window.reliefDesktop.getPathForFile(file)
                      : ''
                    if (droppedPath.toLowerCase().endsWith('.json')) {
                      setRuntime((current) => ({ ...current, workflow_path: droppedPath }))
                    } else {
                      setMessage('请拖入本机的 ComfyUI workflow JSON 文件。')
                    }
                  }}
                >
                  <FileJson size={22} />
                  <span>拖入工作流 JSON，或点击上方文件按钮</span>
                </div>
                <button className="primary-button" type="button" aria-label="分析并测试连接" disabled={Boolean(busy) || !isDesktop()} onClick={() => void verifyWorkflow()}>
                  {busy === 'workflow' ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />}
                  保存、分析并测试
                </button>
                {workflowReport && <div className="workflow-report"><Check size={17} /><div><strong>工作流可用</strong><span>{String((workflowReport.analysis as Record<string, unknown>)?.adapter_mode ?? (workflowReport.analysis as Record<string, unknown>)?.workflow_format ?? '已识别')} · {String((workflowReport.analysis as Record<string, unknown>)?.node_count ?? '?')} 个节点</span></div></div>}
              </div>
            )}

            {tab === 'image' && (
              <div className="settings-section">
                <div><h3>G2 四宫格参考图</h3><p>与模型站点使用同一把 RunningHub key，生成后自动交给 LTX 工作流。</p></div>
                <div className="image-provider-summary"><ImageIcon size={22} /><div><strong>rhart-image-g-2</strong><span>任务式便捷 API · 默认 2K</span></div></div>
                <div className="field-stack"><span>服务站点</span><div className="segmented-control"><button type="button" className={runDraft.runninghubSite === 'cn' ? 'is-active' : ''} onClick={() => patchRunDraft({ runninghubSite: 'cn', stageModels: createRunningHubStageModels('cn') })}>国内站 .cn</button><button type="button" className={runDraft.runninghubSite === 'ai' ? 'is-active' : ''} onClick={() => patchRunDraft({ runninghubSite: 'ai', stageModels: createRunningHubStageModels('ai') })}>国际站 .ai</button></div></div>
                <div className="field-stack"><span>画面比例</span><div className="segmented-control"><button type="button" className={runDraft.aspectRatio === '16:9' ? 'is-active' : ''} onClick={() => patchRunDraft({ aspectRatio: '16:9' })}>横屏 16:9</button><button type="button" className={runDraft.aspectRatio === '9:16' ? 'is-active' : ''} onClick={() => patchRunDraft({ aspectRatio: '9:16' })}>竖屏 9:16</button></div></div>
                <label className="field-stack"><span>生成清晰度</span><select value={runDraft.imageResolution} onChange={(event) => patchRunDraft({ imageResolution: event.target.value as '1k' | '2k' })}><option value="2k">2K 清晰（默认）</option><option value="1k">1K 快速</option></select></label>
                <div className={`inline-notice ${secretStatus[runDraft.runninghubSite === 'cn' ? 'RUNNINGHUB_CN_API_KEY' : 'RUNNINGHUB_AI_API_KEY']?.configured ? '' : 'is-warning'}`}>{secretStatus[runDraft.runninghubSite === 'cn' ? 'RUNNINGHUB_CN_API_KEY' : 'RUNNINGHUB_AI_API_KEY']?.configured ? '当前站点密钥已配置。' : '当前站点还没有配置 RunningHub 密钥。'}</div>
              </div>
            )}

            {tab === 'storage' && (
              <div className="settings-section">
                <div>
                  <h3>执行与存储</h3>
                  <p>控制本地并发和产物目录；保存后由新 sidecar 参数实际生效。</p>
                </div>
                <label className="field-stack">
                  <span>默认输出目录</span>
                  <div className="input-action-row">
                    <input value={runtime.output_root ?? ''} onChange={(event) => setRuntime((current) => ({ ...current, output_root: event.target.value }))} />
                    <button className="icon-button" type="button" onClick={() => void pickOutputRoot()} aria-label="选择输出目录">
                      <FolderOpen size={18} />
                    </button>
                  </div>
                </label>
                <div className="endpoint-grid">
                  <label className="field-stack"><span>并行任务数</span><input type="number" min={1} max={8} value={runtime.max_workers ?? 2} onChange={(event) => setRuntime((current) => ({ ...current, max_workers: Number(event.target.value) }))} /></label>
                  <label className="field-stack"><span>同时生成参考图</span><input type="number" min={1} max={4} value={runtime.image_generation_concurrency ?? 2} onChange={(event) => setRuntime((current) => ({ ...current, image_generation_concurrency: Number(event.target.value) }))} /></label>
                  <label className="field-stack"><span>同时提交 ComfyUI</span><input type="number" min={1} max={4} value={runtime.comfyui_submission_concurrency ?? 1} onChange={(event) => setRuntime((current) => ({ ...current, comfyui_submission_concurrency: Number(event.target.value) }))} /></label>
                </div>
                <button className="primary-button" type="button" disabled={Boolean(busy) || !isDesktop()} onClick={() => void saveRuntime()}>
                  {busy === 'runtime' ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />}
                  保存并应用执行设置
                </button>
              </div>
            )}

            {tab === 'diagnostics' && (
              <div className="settings-section">
                <div>
                  <h3>运行诊断</h3>
                  <p>只有排查问题时才需要查看这里。</p>
                </div>
                <div className="diagnostic-line">
                  <span>本地后端</span>
                  <strong className={health.isSuccess ? 'status-good' : 'status-bad'}>
                    {health.isLoading ? '检查中…' : health.isSuccess ? '在线' : '离线'}
                  </strong>
                </div>
                <div className="diagnostic-line"><span>API 地址</span><strong>{handshake?.backendUrl || '尚未握手'}</strong></div>
                <div className="diagnostic-line"><span>桌面版本</span><strong>{handshake?.version || '未知'}</strong></div>
                {handshake?.backendLastError && <div className="inline-notice is-error">{handshake.backendLastError}</div>}
                {diagnosisReport && (
                  <div className={`diagnosis-card ${diagnosisFailed > 0 ? 'is-error' : 'is-ok'}`}>
                    <div>
                      <strong>{diagnosisFailed > 0 ? '深度诊断发现阻塞' : '深度诊断通过'}</strong>
                      <span>通过 {diagnosisPassed} · 警告 {diagnosisWarnings} · 失败 {diagnosisFailed}</span>
                    </div>
                    {visibleDiagnosisChecks.length > 0 && (
                      <ul className="diagnosis-check-list">
                        {visibleDiagnosisChecks.map((check) => (
                          <li key={check.name}>
                            <b>{check.name}</b>
                            <span>{check.message}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
                <div className="settings-action-row">
                <button
                  className="primary-button"
                  type="button"
                  disabled={Boolean(busy)}
                  onClick={() => void runDeepDiagnosis()}
                >
                  {busy === 'diagnosis' ? <LoaderCircle className="spin" size={17} /> : <ScrollText size={17} />}
                  运行深度诊断
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  disabled={!isDesktop() || Boolean(busy)}
                  onClick={async () => {
                    setBusy('restart')
                    setMessage('正在重启本地后端…')
                    try {
                      const nextHandshake = await window.reliefDesktop?.restartBackend()
                      if (nextHandshake) {
                        setHandshake(nextHandshake)
                        applyDesktopHandshake(nextHandshake)
                      }
                      await health.refetch()
                      setMessage('本地后端已重启。')
                    } catch (error) {
                      setMessage(error instanceof Error ? error.message : '重启失败')
                    } finally {
                      setBusy('')
                    }
                  }}
                >
                  {busy === 'restart' ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={17} />}
                  重启并重新检测
                </button>
                <button className="secondary-button" type="button" disabled={!handshake?.backendLogPath} onClick={() => handshake?.backendLogPath && void window.reliefDesktop?.openPath(handshake.backendLogPath)}><FolderOpen size={16} /> 打开日志</button>
                </div>
              </div>
            )}

            {message && <div className="settings-message" role="status">{message}</div>}
          </div>
        </div>
      </section>
    </div>
  )
}
