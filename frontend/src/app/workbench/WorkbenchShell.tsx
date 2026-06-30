import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  Boxes,
  ChefHat,
  FolderArchive,
  Gauge,
  Settings2,
} from 'lucide-react'
import { AdvancedSettingsDrawer } from '../../features/settings/AdvancedSettingsDrawer'
import { DesktopTitlebar } from '../../shared/components/DesktopTitlebar'
import { useBackendHealth } from '../../shared/hooks/useBackendHealth'
import { WorkbenchContext } from './workbench.context'

const navItems = [
  { path: '/', label: '控制台', icon: Gauge, end: true },
  { path: '/autopilot', label: '自动执行', icon: ChefHat, end: false },
  { path: '/tasks', label: '任务队列', icon: Boxes, end: false },
  { path: '/assets', label: '资产库', icon: FolderArchive, end: false },
] as const

export function WorkbenchShell() {
  const [settingsOpen, setSettingsOpen] = useState(false)
  const health = useBackendHealth()

  return (
    <WorkbenchContext.Provider value={{ openSettings: () => setSettingsOpen(true) }}>
      <div className="workbench-shell">
        <DesktopTitlebar />
        <header className="floating-nav-shell">
          <nav className="floating-nav" aria-label="工作台导航">
            <NavLink className="brand-mark" to="/" aria-label="Relief Story Agent 首页">
              <span>RS</span>
            </NavLink>
            <div className="nav-links">
              {navItems.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.end}
                    className={({ isActive }) => isActive ? 'is-active' : ''}
                  >
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </NavLink>
                )
              })}
            </div>
            <div className="nav-actions">
              <div className="backend-indicator" title={health.isSuccess ? '本地后端在线' : '本地后端离线'}>
                <span className={health.isSuccess ? 'is-online' : 'is-offline'} />
                <span>{health.isSuccess ? '在线' : '离线'}</span>
              </div>
              <button type="button" className="settings-trigger" onClick={() => setSettingsOpen(true)} aria-label="高级设置">
                <Settings2 size={17} />
                <span>高级设置</span>
              </button>
            </div>
          </nav>
        </header>

        <main className="workbench-main">
          <Outlet />
        </main>

        <AdvancedSettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      </div>
    </WorkbenchContext.Provider>
  )
}
