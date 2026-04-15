import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, Clock, Monitor, Trash2 } from 'lucide-react'
import { Card, CardContent } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { RunStatusBadge } from '../components/ui/StatusBadge'
import { Badge } from '../components/ui/Badge'
import { Select } from '../components/ui/FormFields'
import { EmptyState, PageLoader, PageError } from '../components/ui/EmptyState'
import { runApi } from '../services/api'
import type { TestRun } from '../types'
import { formatDistanceToNow, format } from 'date-fns'

export function TestRunsPage() {
  const navigate = useNavigate()
  const [runs, setRuns] = useState<TestRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')

  const loadRuns = (silent = false) => {
    if (!silent) setLoading(true)
    setError(null)
    runApi.list(statusFilter ? { status_filter: statusFilter } : undefined)
      .then(setRuns)
      .catch(e => setError(e.message))
      .finally(() => { if (!silent) setLoading(false) })
  }

  useEffect(() => { loadRuns() }, [statusFilter])

  // Poll every 3 s while any run is still active so the list auto-updates
  useEffect(() => {
    const hasActiveRuns = runs.some(r => r.status === 'running' || r.status === 'pending')
    if (!hasActiveRuns) return
    const id = setInterval(() => loadRuns(true), 3000)
    return () => clearInterval(id)
  }, [runs, statusFilter])

  if (loading) return <PageLoader />
  if (error) return <PageError message={error} onRetry={loadRuns} />

  const sorted = [...runs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Test Runs"
        description="Monitor and review all test execution results"
        actions={
          <Select
            id="status-filter"
            options={[
              { value: '', label: 'All Statuses' },
              { value: 'pending', label: 'Pending' },
              { value: 'running', label: 'Running' },
              { value: 'passed', label: 'Passed' },
              { value: 'failed', label: 'Failed' },
              { value: 'error', label: 'Error' },
            ]}
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          />
        }
      />

      {sorted.length === 0 ? (
        <EmptyState
          icon={Play}
          title="No test runs"
          description="Run a test case to see execution results here."
        />
      ) : (
        <div className="space-y-2">
          {sorted.map(run => (
            <Card key={run.id} hover onClick={() => navigate(`/runs/${run.id}`)}>
              <CardContent className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <RunStatusBadge status={run.status} />
                  <div>
                    <p className="text-sm font-medium text-surface-200">
                      Run {run.id.slice(0, 8)}
                    </p>
                    <p className="text-xs text-surface-500">
                      Case: {run.case_id.slice(0, 8)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-1.5 text-xs text-surface-400">
                    <Monitor className="w-3 h-3" />
                    {run.browser}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-surface-400">
                    <Clock className="w-3 h-3" />
                    {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '—'}
                  </div>
                  <span className="text-xs text-surface-500 w-24 text-right">
                    {formatDistanceToNow(new Date(run.created_at), { addSuffix: true })}
                  </span>
                  <button
                    onClick={e => {
                      e.stopPropagation()
                      if (confirm('Delete this test run?')) {
                        runApi.delete(run.id).then(() => loadRuns())
                      }
                    }}
                    className="p-1.5 rounded-lg text-surface-600 hover:text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer"
                    title="Delete run"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
