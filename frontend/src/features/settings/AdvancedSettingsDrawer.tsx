import { useEffect, useMemo, useState } from 'react'
import {
  Check,
  ChevronRight,
  Eye,
  EyeOff,
  FileJson,
  FolderOpen,
  KeyRound,
  LoaderCircle,
  RefreshCw,
  ServerCog,
  X,
} from 'lucide-react'
import { useBackendHealth } from '../../shared/hooks/useBackendHealth'

type SettingsTab = 'secrets' | 'comfyui' | 'storage' | 'diagnostics'
type SecretStatus = Record<string, { configured: boolean; masked: string }>
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
  const health = useBackendHealth()

  useEffect(() => {
    if (!open || !window.reliefDesktop) return
    setMessage('')
    void Promise.all([
      window.reliefDesktop.getRuntimeConfig(),
      window.reliefDesktop.getSecretStatus(),
    ]).then(([savedRuntime, savedStatus]) => {
      setRuntime((current) => ({ ...current, ...(savedRuntime as RuntimeConfig) }))
      setSecretStatus(savedStatus)
    }).catch((error: unknown) => {
      setMessage(error instanceof Error ? error.message : '无法读取桌面设置')
    })
  }, [open])

  useEffect(() => {
    if (!open) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
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

  const saveRuntime = async () => {
    if (!window.reliefDesktop) return
    setBusy('runtime')
    setMessage('正在保存配置并重启本地后端…')
    try {
      const result = await window.reliefDesktop.saveRuntimeConfig(runtime)
      const config = result.config as RuntimeConfig
      setRuntime((current) => ({ ...current, ...config }))
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

  const tabs: Array<{ id: SettingsTab; label: string; icon: typeof KeyRound }> = [
    { id: 'secrets', label: '模型与密钥', icon: KeyRound },
    { id: 'comfyui', label: 'ComfyUI', icon: ServerCog },
    { id: 'storage', label: '输出与存储', icon: FolderOpen },
    { id: 'diagnostics', label: '诊断', icon: RefreshCw },
  ]

  return (
    <div className="settings-backdrop" role="presentation" onMouseDown={onClose}>
      <section
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
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭高级设置">
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
                <button className="primary-button" type="button" disabled={Boolean(busy) || !isDesktop()} onClick={() => void saveRuntime()}>
                  {busy === 'runtime' ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />}
                  保存并重启本地后端
                </button>
              </div>
            )}

            {tab === 'storage' && (
              <div className="settings-section">
                <div>
                  <h3>输出与存储</h3>
                  <p>所有剧本、提示词、参考图和视频会按任务归档。</p>
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
                <button className="primary-button" type="button" disabled={Boolean(busy) || !isDesktop()} onClick={() => void saveRuntime()}>
                  {busy === 'runtime' ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />}
                  保存输出目录
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
                <button
                  className="secondary-button"
                  type="button"
                  disabled={!isDesktop() || Boolean(busy)}
                  onClick={async () => {
                    setBusy('restart')
                    setMessage('正在重启本地后端…')
                    try {
                      await window.reliefDesktop?.restartBackend()
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
              </div>
            )}

            {message && <div className="settings-message" role="status">{message}</div>}
          </div>
        </div>
      </section>
    </div>
  )
}
