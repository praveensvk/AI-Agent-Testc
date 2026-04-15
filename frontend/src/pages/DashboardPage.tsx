import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FolderKanban,
  FileCheck2,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  Activity,
} from 'lucide-react'
import { Card, CardContent } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { PageLoader } from '../components/ui/EmptyState'
import { RunStatusBadge } from '../components/ui/StatusBadge'
import { suiteApi, runApi } from '../services/api'
import type { TestSuite, TestRun } from '../types'
import { formatDistanceToNow } from 'date-fns'

export function DashboardPage() {
  const navigate = useNavigate()
  const [suites, setSuites] = useState<TestSuite[]>([])
  const [runs, setRuns] = useState<TestRun[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([suiteApi.list(), runApi.list()])
      .then(([s, r]) => {
        setSuites(s)
        setRuns(r)
      })
      .finally(() => setLoading(false))
  }, [])

  // Poll every 3 s while any run is still active
  useEffect(() => {
    const hasActiveRuns = runs.some(r => r.status === 'running' || r.status === 'pending')
    if (!hasActiveRuns) return
    const id = setInterval(() => {
      runApi.list().then(setRuns).catch(() => {})
    }, 3000)
    return () => clearInterval(id)
  }, [runs])

  if (loading) return <PageLoader />

  const totalCases = suites.length * 3 // approximation, will refine
  const passedRuns = runs.filter(r => r.status === 'passed').length
  const failedRuns = runs.filter(r => r.status === 'failed' || r.status === 'error').length
  const recentRuns = [...runs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 8)
  const passRate = runs.length > 0 ? Math.round((passedRuns / runs.length) * 100) : 0

  const stats = [
    { label: 'Test Suites', value: suites.length, icon: FolderKanban, color: 'text-blue-400', bg: 'bg-blue-500/10' },
    { label: 'Total Runs', value: runs.length, icon: Play, color: 'text-purple-400', bg: 'bg-purple-500/10' },
    { label: 'Passed', value: passedRuns, icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    { label: 'Failed', value: failedRuns, icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10' },
  ]

  return (
    <div className="animate-fade-in space-y-6">
      <PageHeader
        title="Dashboard"
        description="Overview of your AI-powered test automation platform"
      />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(stat => (
          <Card key={stat.label}>
            <CardContent className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl ${stat.bg} flex items-center justify-center`}>
                <stat.icon className={`w-6 h-6 ${stat.color}`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-surface-50">{stat.value}</p>
                <p className="text-xs text-surface-400">{stat.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pass Rate */}
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-8">
            <div className="relative w-28 h-28 mb-4">
              <svg className="w-28 h-28 -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="8" className="text-surface-800" />
                <circle
                  cx="50" cy="50" r="42" fill="none" strokeWidth="8"
                  strokeDasharray={`${passRate * 2.64} 264`}
                  strokeLinecap="round"
                  className={passRate >= 70 ? 'text-emerald-500' : passRate >= 40 ? 'text-amber-500' : 'text-red-500'}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center flex-col">
                <span className="text-2xl font-bold text-surface-50">{passRate}%</span>
              </div>
            </div>
            <div className="flex items-center gap-2 text-surface-400">
              <TrendingUp className="w-4 h-4" />
              <span className="text-sm">Pass Rate</span>
            </div>
          </CardContent>
        </Card>

        {/* Recent Runs */}
        <Card className="lg:col-span-2">
          <div className="px-5 py-4 border-b border-surface-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-surface-400" />
              <h3 className="text-sm font-semibold text-surface-200">Recent Test Runs</h3>
            </div>
            <button
              onClick={() => navigate('/runs')}
              className="text-xs text-primary-400 hover:text-primary-300 cursor-pointer"
            >
              View all
            </button>
          </div>
          <div className="divide-y divide-surface-800">
            {recentRuns.length === 0 ? (
              <div className="px-5 py-8 text-center text-sm text-surface-500">
                No test runs yet. Create a suite and run your first test!
              </div>
            ) : (
              recentRuns.map(run => (
                <div
                  key={run.id}
                  className="px-5 py-3 flex items-center justify-between hover:bg-surface-800/50 cursor-pointer transition-colors"
                  onClick={() => navigate(`/runs/${run.id}`)}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <RunStatusBadge status={run.status} />
                    <div className="min-w-0">
                      <p className="text-sm text-surface-200 truncate">{run.case_id.slice(0, 8)}...</p>
                      <p className="text-xs text-surface-500">
                        {run.browser} • {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '—'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-surface-500">
                    <Clock className="w-3 h-3" />
                    {formatDistanceToNow(new Date(run.created_at), { addSuffix: true })}
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* Suites Quick List */}
      <Card>
        <div className="px-5 py-4 border-b border-surface-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FolderKanban className="w-4 h-4 text-surface-400" />
            <h3 className="text-sm font-semibold text-surface-200">Test Suites</h3>
          </div>
          <button
            onClick={() => navigate('/suites')}
            className="text-xs text-primary-400 hover:text-primary-300 cursor-pointer"
          >
            Manage suites
          </button>
        </div>
        <div className="divide-y divide-surface-800">
          {suites.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-surface-500">
              No test suites created yet.
            </div>
          ) : (
            suites.slice(0, 5).map(suite => (
              <div
                key={suite.id}
                className="px-5 py-3 flex items-center justify-between hover:bg-surface-800/50 cursor-pointer transition-colors"
                onClick={() => navigate(`/suites/${suite.id}`)}
              >
                <div>
                  <p className="text-sm font-medium text-surface-200">{suite.name}</p>
                  <p className="text-xs text-surface-500 truncate max-w-md">{suite.base_url}</p>
                </div>
                <span className="text-xs text-surface-500">
                  {formatDistanceToNow(new Date(suite.updated_at), { addSuffix: true })}
                </span>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  )
}
