import { Button } from '@heroui/react'
import { FolderOpen, RotateCcw, Save, SlidersHorizontal } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import { getDesktopBridge } from '../../../shared/desktop/desktopBridge'
import { useUiStore } from '../../../shared/store/uiStore'
import type {
  DesktopSettings,
  DesktopState,
} from '../../../shared/contracts/desktop.contract'

type FormState = {
  host: string
  backendPort: string
  frontendPort: string
  comfyUiEndpoint: string
  workflowPath: string
  stateDir: string
  logDir: string
}

const fallbackForm: FormState = {
  host: '127.0.0.1',
  backendPort: '8891',
  frontendPort: '5173',
  comfyUiEndpoint: 'http://127.0.0.1:8188',
  workflowPath: 'D:/ComfyUI/workflows/ltx23_four_grid.json',
  stateDir: '',
  logDir: '',
}

function toForm(settings: DesktopSettings): FormState {
  return {
    host: settings.host,
    backendPort: String(settings.backendPort),
    frontendPort: String(settings.frontendPort),
    comfyUiEndpoint: settings.comfyUiEndpoint,
    workflowPath: settings.workflowPath,
    stateDir: settings.stateDir,
    logDir: settings.logDir,
  }
}

function toSettings(form: FormState): DesktopSettings {
  return {
    host: form.host.trim(),
    backendPort: Number(form.backendPort),
    frontendPort: Number(form.frontendPort),
    comfyUiEndpoint: form.comfyUiEndpoint.trim(),
    workflowPath: form.workflowPath.trim(),
    stateDir: form.stateDir.trim(),
    logDir: form.logDir.trim(),
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export function DesktopSettingsPanel() {
  const bridge = useMemo(() => getDesktopBridge(), [])
  const setApiBaseUrl = useUiStore((state) => state.setApiBaseUrl)
  const setRecentComfyUIEndpoint = useUiStore(
    (state) => state.setRecentComfyUIEndpoint,
  )
  const setRecentWorkflowPath = useUiStore((state) => state.setRecentWorkflowPath)
  const [desktopState, setDesktopState] = useState<DesktopState | null>(null)
  const [form, setForm] = useState<FormState>(fallbackForm)
  const [isBusy, setIsBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const syncState = (state: DesktopState) => {
    setDesktopState(state)
    setForm(toForm(state.settings))
    setApiBaseUrl(state.backendUrl)
    setRecentComfyUIEndpoint(state.settings.comfyUiEndpoint)
    setRecentWorkflowPath(state.settings.workflowPath)
  }

  useEffect(() => {
    if (!bridge) return

    let mounted = true
    bridge.settings
      .load()
      .then((state) => {
        if (mounted) syncState(state)
      })
      .catch((loadError: unknown) => {
        if (mounted) setError(errorMessage(loadError))
      })
    return () => {
      mounted = false
    }
  }, [bridge])

  const updateField =
    (key: keyof FormState) =>
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setForm((current) => ({ ...current, [key]: event.target.value }))
      setMessage('')
      setError('')
    }

  const save = async (restart: boolean) => {
    if (!bridge) return
    setIsBusy(true)
    setMessage('')
    setError('')
    try {
      const savedState = await bridge.settings.save(toSettings(form))
      syncState(savedState)
      if (restart) {
        const restartedState = await bridge.backend.restart()
        syncState(restartedState)
        setMessage('配置已保存，后端已按新设置重启。')
      } else {
        setMessage('配置已保存。')
      }
    } catch (saveError) {
      setError(errorMessage(saveError))
    } finally {
      setIsBusy(false)
    }
  }

  const reset = async () => {
    if (!bridge) return
    setIsBusy(true)
    setMessage('')
    setError('')
    try {
      const state = await bridge.settings.reset()
      syncState(state)
      setMessage('已恢复默认桌面配置。')
    } catch (resetError) {
      setError(errorMessage(resetError))
    } finally {
      setIsBusy(false)
    }
  }

  const openLogs = async () => {
    if (!bridge) return
    setIsBusy(true)
    setMessage('')
    setError('')
    try {
      const result = await bridge.logs.open()
      if (result.opened) {
        setMessage(`已打开日志目录：${result.path}`)
      } else {
        setError(result.error || '无法打开日志目录。')
      }
    } catch (openError) {
      setError(errorMessage(openError))
    } finally {
      setIsBusy(false)
    }
  }

  const disabled = !bridge || isBusy

  return (
    <SectionCard
      title="桌面客户端设置"
      description="保存本机端口、ComfyUI 和数据目录；需要生效时重启本地服务。"
      tone="blue"
      action={
        <StatusBadge
          status={bridge ? 'ready' : 'warning'}
          label={bridge ? 'Electron' : '浏览器预览'}
        />
      }
    >
      {!bridge ? (
        <div className="alert-box alert-box--soft">
          <h3>桌面客户端功能不可用</h3>
          <p>请从 Electron 桌面客户端打开，才能保存配置和重启本地服务。</p>
        </div>
      ) : null}

      <div className="desktop-settings__summary">
        <div className="metric metric--wide metric--code">
          <span>后端地址</span>
          <strong>{desktopState?.backendUrl ?? '未读取'}</strong>
        </div>
        <div className="metric metric--wide metric--code">
          <span>配置文件</span>
          <strong>{desktopState?.settingsPath ?? '等待桌面桥接'}</strong>
        </div>
        <div className="metric">
          <span>服务状态</span>
          <strong>
            <StatusBadge
              status={desktopState?.backendRunning ? 'ready' : 'warning'}
              label={desktopState?.backendRunning ? '运行中' : '未确认'}
            />
          </strong>
        </div>
      </div>

      <div className="desktop-settings__form">
        <div className="field">
          <label htmlFor="desktop-host">Host</label>
          <input
            id="desktop-host"
            value={form.host}
            onChange={updateField('host')}
            disabled={disabled}
          />
        </div>
        <div className="field">
          <label htmlFor="desktop-backend-port">后端端口</label>
          <input
            id="desktop-backend-port"
            inputMode="numeric"
            value={form.backendPort}
            onChange={updateField('backendPort')}
            disabled={disabled}
          />
        </div>
        <div className="field">
          <label htmlFor="desktop-frontend-port">前端端口</label>
          <input
            id="desktop-frontend-port"
            inputMode="numeric"
            value={form.frontendPort}
            onChange={updateField('frontendPort')}
            disabled={disabled}
          />
        </div>
        <div className="field field--wide">
          <label htmlFor="desktop-comfy">ComfyUI 地址</label>
          <input
            id="desktop-comfy"
            value={form.comfyUiEndpoint}
            onChange={updateField('comfyUiEndpoint')}
            disabled={disabled}
          />
        </div>
        <div className="field field--wide">
          <label htmlFor="desktop-workflow">Workflow Path</label>
          <input
            id="desktop-workflow"
            value={form.workflowPath}
            onChange={updateField('workflowPath')}
            disabled={disabled}
          />
        </div>
        <div className="field field--wide">
          <label htmlFor="desktop-state-dir">State Directory</label>
          <input
            id="desktop-state-dir"
            value={form.stateDir}
            onChange={updateField('stateDir')}
            disabled={disabled}
          />
        </div>
        <div className="field field--wide">
          <label htmlFor="desktop-log-dir">Log Directory</label>
          <input
            id="desktop-log-dir"
            value={form.logDir}
            onChange={updateField('logDir')}
            disabled={disabled}
          />
        </div>
      </div>

      {error ? (
        <div className="alert-box alert-box--danger" role="alert">
          <h3>保存失败</h3>
          <p>{error}</p>
        </div>
      ) : null}
      {message ? (
        <div className="alert-box alert-box--success" role="status">
          <h3>{message}</h3>
        </div>
      ) : null}

      <div className="desktop-settings__actions">
        <Button
          className="hero-button"
          isDisabled={disabled}
          onPress={() => void save(true)}
        >
          <SlidersHorizontal size={16} />
          保存并重启本地服务
        </Button>
        <Button
          className="secondary-button"
          isDisabled={disabled}
          onPress={() => void save(false)}
        >
          <Save size={16} />
          仅保存
        </Button>
        <Button className="ghost-button" isDisabled={disabled} onPress={openLogs}>
          <FolderOpen size={16} />
          打开日志目录
        </Button>
        <Button className="ghost-button" isDisabled={disabled} onPress={reset}>
          <RotateCcw size={16} />
          重置默认值
        </Button>
      </div>
    </SectionCard>
  )
}
