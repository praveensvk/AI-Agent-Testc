import { useEffect, useState } from 'react'
import {
  BarChart3,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Clock,
  Monitor,
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { Badge } from '../components/ui/Badge'
import { PageLoader } from '../components/ui/EmptyState'
import { runApi, suiteApi } from '../services/api'
import type { TestRun, TestSuite } from '../types'

export function ReportsPage() {
  const [runs, setRuns] = useState<TestRun[]>([])
  const [suites, setSuites] = useState<TestSuite[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([runApi.list(), suiteApi.list()])
      .then(([r, s]) => { setRuns(r); setSuites(s) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <PageLoader />

  const total = runs.length
  const passed = runs.filter(r => r.status === 'passed').length
  const failed = runs.filter(r => r.status === 'failed' || r.status === 'error').length
  const passRate = total > 0 ? Math.round((passed / total) * 100) : 0
  const avgDuration = runs.filter(r => r.duration_ms).reduce((sum, r) => sum + (r.duration_ms || 0), 0) / (runs.filter(r => r.duration_ms).length || 1)

  // Browser breakdown
  const browserCounts: Record<string, { total: number; passed: number }> = {}
  runs.forEach(r => {
    if (!browserCounts[r.browser]) browserCounts[r.browser] = { total: 0, passed: 0 }
    browserCounts[r.browser].total++
    if (r.status === 'passed') browserCounts[r.browser].passed++
  })

  // Daily run counts (last 7 items by date)
  const dailyCounts: Record<string, { passed: number; failed: number }> = {}
  runs.forEach(r => {
    const day = r.created_at.slice(0, 10)
    if (!dailyCounts[day]) dailyCounts[day] = { passed: 0, failed: 0 }
    if (r.status === 'passed') dailyCounts[day].passed++
    else if (r.status === 'failed' || r.status === 'error') dailyCounts[day].failed++
  })
  const recentDays = Object.entries(dailyCounts)
    .sort(([a], [b]) => b.localeCompare(a))
    .slice(0, 7)
    .reverse()

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Reports"
        description="Analytics and insights from your test automation"
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="text-center py-5">
            <BarChart3 className="w-6 h-6 text-blue-400 mx-auto mb-2" />
            <p className="text-3xl font-bold text-surface-50">{total}</p>
            <p className="text-xs text-surface-400">Total Runs</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-center py-5">
            <TrendingUp className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
            <p className="text-3xl font-bold text-emerald-400">{passRate}%</p>
            <p className="text-xs text-surface-400">Pass Rate</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-center py-5">
            <Clock className="w-6 h-6 text-amber-400 mx-auto mb-2" />
            <p className="text-3xl font-bold text-surface-50">{(avgDuration / 1000).toFixed(1)}s</p>
            <p className="text-xs text-surface-400">Avg Duration</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-center py-5">
            <Monitor className="w-6 h-6 text-purple-400 mx-auto mb-2" />
            <p className="text-3xl font-bold text-surface-50">{suites.length}</p>
            <p className="text-xs text-surface-400">Active Suites</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Activity */}
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-surface-200">Daily Activity</h3>
          </CardHeader>
          <CardContent>
            {recentDays.length === 0 ? (
              <p className="text-sm text-surface-500 text-center py-4">No data yet</p>
            ) : (
              <div className="space-y-3">
                {recentDays.map(([day, counts]) => {
                  const dayTotal = counts.passed + counts.failed
                  const maxBar = Math.max(...recentDays.map(([, c]) => c.passed + c.failed), 1)
                  return (
                    <div key={day} className="flex items-center gap-3">
                      <span className="text-xs text-surface-400 w-20">{day.slice(5)}</span>
                      <div className="flex-1 flex gap-0.5 h-5">
                        <div
                          className="bg-emerald-500/60 rounded-l"
                          style={{ width: `${(counts.passed / maxBar) * 100}%` }}
                        />
                        <div
                          className="bg-red-500/60 rounded-r"
                          style={{ width: `${(counts.failed / maxBar) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-surface-500 w-8 text-right">{dayTotal}</span>
                    </div>
                  )
                })}
                <div className="flex items-center gap-4 pt-2">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded bg-emerald-500/60" />
                    <span className="text-xs text-surface-400">Passed</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded bg-red-500/60" />
                    <span className="text-xs text-surface-400">Failed</span>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Browser Breakdown */}
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-surface-200">Browser Breakdown</h3>
          </CardHeader>
          <CardContent>
            {Object.keys(browserCounts).length === 0 ? (
              <p className="text-sm text-surface-500 text-center py-4">No data yet</p>
            ) : (
              <div className="space-y-4">
                {Object.entries(browserCounts).map(([browser, counts]) => {
                  const rate = Math.round((counts.passed / counts.total) * 100)
                  return (
                    <div key={browser}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-sm text-surface-200 capitalize">{browser}</span>
                        <span className="text-xs text-surface-400">{counts.total} runs • {rate}% pass</span>
                      </div>
                      <div className="w-full h-2 bg-surface-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary-500 rounded-full transition-all"
                          style={{ width: `${rate}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
