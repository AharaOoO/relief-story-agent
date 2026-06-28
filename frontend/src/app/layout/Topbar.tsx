import { ShieldCheck, Sparkles } from 'lucide-react'
import { useUiStore } from '../../shared/store/uiStore'

const guardrailText =
  'readiness first / preflight before real run / recovery plan before recover / no raw api keys / '

export function Topbar() {
  const apiBaseUrl = useUiStore((state) => state.apiBaseUrl)
  const setApiBaseUrl = useUiStore((state) => state.setApiBaseUrl)

  return (
    <>
      <div className="marquee-strip" aria-hidden="true">
        <span>{guardrailText}</span>
        <span>{guardrailText}</span>
      </div>
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Sparkles size={25} />
          </div>
          <div>
            <div className="brand-title display-font">Relief Story</div>
            <strong>Desktop Client</strong>
          </div>
        </div>
        <div className="topbar-note" aria-label="当前桌面工作台原则">
          <ShieldCheck size={18} />
          <span>本地创作工作台</span>
          <strong>配置、运行、恢复都在眼前</strong>
        </div>
        <div className="api-control">
          <label htmlFor="api-base-url">后端 API 地址</label>
          <input
            id="api-base-url"
            aria-label="后端 API 地址"
            title="输入后端服务地址，例如 http://127.0.0.1:8891"
            value={apiBaseUrl}
            onChange={(event) => setApiBaseUrl(event.target.value)}
          />
        </div>
      </header>
    </>
  )
}
