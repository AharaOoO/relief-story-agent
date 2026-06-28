import { CopyButton } from '../../../shared/components/CopyButton'
import { SectionCard } from '../../../shared/components/SectionCard'

const desktopShortcut = 'Relief Story Agent Desktop.lnk'
const desktopShortcutPath = 'C:/Users/dcf/Desktop/Relief Story Agent Desktop.lnk'
const browserUrl = 'http://127.0.0.1:5173'
const backendUrl = 'http://127.0.0.1:8891'
const comfyUiUrl = 'http://127.0.0.1:8188'
const launcherLogs = 'D:/codex工作区/relief_story_state/launcher-logs'

export function LaunchGuideCard() {
  return (
    <SectionCard
      title="打开与端口"
      description="软件入口、网页备用地址、后端端口和 ComfyUI 端口放在同一张地图里。"
      action={<CopyButton value={desktopShortcutPath} label="复制桌面快捷方式路径" />}
    >
      <div className="guide-grid">
        <div className="guide-item">
          <span>单独软件端</span>
          <strong>{desktopShortcut}</strong>
          <p>优先从桌面点这个，它会打开 Electron 桌面窗口。</p>
        </div>
        <div className="guide-item">
          <span>网页备用入口</span>
          <strong>{browserUrl}</strong>
          <p>如果只想用浏览器，打开这个前端地址。</p>
        </div>
        <div className="guide-item">
          <span>后端 API / 端口</span>
          <strong>{backendUrl}</strong>
          <p>右上角输入框改的就是这个地址和端口。</p>
        </div>
        <div className="guide-item">
          <span>ComfyUI 端口</span>
          <strong>{comfyUiUrl}</strong>
          <p>在下面的 ComfyUI 连接卡里修改。</p>
        </div>
        <div className="guide-item guide-item--wide">
          <span>启动日志</span>
          <strong>{launcherLogs}</strong>
          <p>打不开或端口被占用时，先看这里的 backend.log / frontend.log。</p>
        </div>
      </div>
    </SectionCard>
  )
}
