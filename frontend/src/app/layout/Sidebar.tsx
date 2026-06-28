import {
  Archive,
  Boxes,
  Film,
  Home,
  ListChecks,
  Settings,
  Wrench,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/local-setup', label: '本地环境', icon: Home },
  { to: '/model-config', label: '模型配置', icon: Settings },
  { to: '/create-run', label: '创作任务', icon: Film },
  { to: '/runs/demo-run/review', label: '分镜审查', icon: ListChecks },
  { to: '/batches', label: '批量队列', icon: Boxes },
  { to: '/artifacts', label: '产物库', icon: Archive },
  { to: '/recovery', label: '故障恢复', icon: Wrench },
]

export function Sidebar() {
  return (
    <aside className="sidebar" aria-label="主导航">
      <p className="sidebar-heading">Workflow menu</p>
      <nav className="nav-list">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink className="nav-link" key={item.to} to={item.to}>
              <span className="nav-icon">
                <Icon size={18} />
              </span>
              <span>{item.label}</span>
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}
