import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { useState } from 'react'
import { Menu } from 'lucide-react'

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`
          fixed inset-y-0 left-0 z-40 w-64 transform transition-transform duration-200 ease-in-out
          lg:relative lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile header */}
        <div className="lg:hidden flex items-center h-14 px-4 border-b border-surface-800 bg-surface-900">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-lg text-surface-400 hover:text-surface-100 hover:bg-surface-800"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="ml-3 font-semibold text-surface-100">TestPilot AI</span>
        </div>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
