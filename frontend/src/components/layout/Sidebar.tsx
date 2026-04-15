import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FolderKanban,
  Play,
  BarChart3,
  Settings,
  X,
  Zap,
} from 'lucide-react'
import { clsx } from 'clsx'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/suites', label: 'Test Suites', icon: FolderKanban },
  { to: '/runs', label: 'Test Runs', icon: Play },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

interface SidebarProps {
  onClose: () => void
}

export function Sidebar({ onClose }: SidebarProps) {
  return (
    <aside className="flex flex-col h-full bg-surface-900 border-r border-surface-800">
      {/* Logo */}
      <div className="flex items-center justify-between h-14 px-4 border-b border-surface-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-lg text-surface-50">TestPilot AI</span>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-surface-400 hover:text-surface-100 hover:bg-surface-800 lg:hidden"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onClose}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-600/15 text-primary-400'
                  : 'text-surface-400 hover:text-surface-100 hover:bg-surface-800'
              )
            }
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-surface-800">
        <p className="text-xs text-surface-500">AI-Powered Test Automation</p>
        <p className="text-xs text-surface-600 mt-0.5">v1.0.0</p>
      </div>
    </aside>
  )
}
