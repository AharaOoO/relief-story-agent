import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { StatusBar } from './StatusBar'
import { Topbar } from './Topbar'

export function AppShell() {
  return (
    <div className="app-shell">
      <Topbar />
      <div className="layout-grid">
        <Sidebar />
        <main className="page-surface">
          <div className="page-inner">
            <Outlet />
          </div>
        </main>
        <StatusBar />
      </div>
    </div>
  )
}
