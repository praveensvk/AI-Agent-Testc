import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Sparkles,
  Play,
  Code2,
  ListOrdered,
  Plus,
  Trash2,
  GripVertical,
  Mouse,
  Type,
  Globe,
  Eye,
  Clock,
  Camera,
  ArrowDown,
  Check,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { CaseStatusBadge, RunStatusBadge } from '../components/ui/StatusBadge'
import { Modal } from '../components/ui/Modal'
import { Input, Select } from '../components/ui/FormFields'
import { PageLoader, PageError } from '../components/ui/EmptyState'
import { TestRunner } from '../components/runner/TestRunner'
import { caseApi, generationApi, runApi, suiteApi } from '../services/api'
import type { TestCaseDetail, TestStep, GenerationStatus, TestRun, UpdateTestStepRequest } from '../types'
import { useTestRunSocket } from '../hooks/useTestRunSocket'

const actionIcons: Record<string, React.ElementType> = {
  click: Mouse,
  type: Type,
  fill: Type,
  navigate: Globe,
  verify_text: Eye,
  verify_element: Eye,
  wait: Clock,
  screenshot: Camera,
  scroll: ArrowDown,
  hover: Mouse,
  press: Type,
  select: ChevronDown,
  clear: Type,
}

const actionOptions = [
  { value: 'navigate', label: 'Navigate' },
  { value: 'click', label: 'Click' },
  { value: 'type', label: 'Type' },
  { value: 'fill', label: 'Fill' },
  { value: 'select', label: 'Select' },
  { value: 'hover', label: 'Hover' },
  { value: 'press', label: 'Press Key' },
  { value: 'clear', label: 'Clear' },
  { value: 'scroll', label: 'Scroll' },
  { value: 'verify_text', label: 'Verify Text' },
  { value: 'verify_element', label: 'Verify Element' },
  { value: 'wait', label: 'Wait' },
  { value: 'screenshot', label: 'Screenshot' },
]

export function CaseDetailPage() {
  const { suiteId, caseId } = useParams<{ suiteId: string; caseId: string }>()
  const navigate = useNavigate()
  const [tc, setTc] = useState<TestCaseDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [genStatus, setGenStatus] = useState<GenerationStatus | null>(null)
  const [code, setCode] = useState<string | null>(null)
  const [showCode, setShowCode] = useState(false)
  const [regeneratingCode, setRegeneratingCode] = useState(false)
  const [activeTab, setActiveTab] = useState<'steps' | 'code' | 'runner'>('steps')
  const [showRunModal, setShowRunModal] = useState(false)
  const [runBrowser, setRunBrowser] = useState('chromium')
  const [creatingRun, setCreatingRun] = useState(false)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [recentRuns, setRecentRuns] = useState<TestRun[]>([])
  const [showEditStep, setShowEditStep] = useState(false)
  const [editingSteps, setEditingSteps] = useState<UpdateTestStepRequest[]>([])
  const [savingSteps, setSavingSteps] = useState(false)
  const [baseUrl, setBaseUrl] = useState<string | undefined>(undefined)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // WebSocket for live run
  const { steps: wsSteps, status: wsStatus, connected: wsConnected, reset: wsReset } = useTestRunSocket(activeRunId)

  const loadCase = () => {
    if (!caseId) return
    setLoading(true)
    setError(null)
    caseApi.get(caseId)
      .then(setTc)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  const loadRuns = () => {
    if (!caseId) return
    runApi.list({ case_id: caseId }).then(setRecentRuns).catch(() => {})
  }

  const loadCode = () => {
    if (!caseId) return
    generationApi.getCode(caseId).then(r => setCode(r.code_content)).catch(() => setCode(null))
  }

  useEffect(() => {
    loadCase()
    loadRuns()
    loadCode()
    // Load base URL from suite
    if (suiteId) {
      suiteApi.get(suiteId).then(s => setBaseUrl(s.base_url)).catch(() => {})
    }
  }, [caseId, suiteId])

  // Poll generation status when generating
  useEffect(() => {
    if (generating && caseId) {
      pollRef.current = setInterval(async () => {
        try {
          const status = await generationApi.status(caseId)
          setGenStatus(status)
          if (status.generation?.status === 'success' || status.generation?.status === 'failed') {
            setGenerating(false)
            clearInterval(pollRef.current!)
            loadCase()
            loadCode()
          }
        } catch {
          // ignore polling errors
        }
      }, 2000)
      return () => { if (pollRef.current) clearInterval(pollRef.current) }
    }
  }, [generating, caseId])

  // When WS run completes, reload runs
  useEffect(() => {
    if (wsStatus === 'passed' || wsStatus === 'failed' || wsStatus === 'error') {
      loadRuns()
    }
  }, [wsStatus])

  // When WS disconnects without a terminal status (e.g. page revisit after completion),
  // reload runs from DB so the sidebar badges show the real final status
  useEffect(() => {
    if (!wsConnected && activeRunId && wsStatus !== 'passed' && wsStatus !== 'failed' && wsStatus !== 'error') {
      loadRuns()
    }
  }, [wsConnected])

  const handleGenerate = async () => {
    if (!caseId) return
    setGenerating(true)
    setGenStatus(null)
    try {
      await generationApi.trigger(caseId)
    } catch (e: any) {
      setGenerating(false)
      setError(e.message)
    }
  }

  const handleRegenerateCode = async () => {
    if (!caseId) return
    setRegeneratingCode(true)
    try {
      const result = await generationApi.regenerateCode(caseId)
      setCode(result.code_content)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setRegeneratingCode(false)
    }
  }

  const handleRunTest = async () => {
    if (!caseId) return
    setCreatingRun(true)
    try {
      const run = await runApi.create({ case_id: caseId, browser: runBrowser as any })
      setActiveRunId(run.id)
      wsReset()
      setShowRunModal(false)
      setActiveTab('runner')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setCreatingRun(false)
    }
  }

  const startEditSteps = () => {
    if (!tc) return
    setEditingSteps(tc.test_steps.map(s => ({
      order: s.order,
      action: s.action,
      selector: s.selector,
      value: s.value,
      expected_result: s.expected_result,
      description: s.description,
    })))
    setShowEditStep(true)
  }

  const handleSaveSteps = async () => {
    if (!caseId) return
    setSavingSteps(true)
    try {
      const updated = await caseApi.updateSteps(caseId, editingSteps)
      setTc(updated)
      setShowEditStep(false)
      loadCode()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSavingSteps(false)
    }
  }

  const addStep = () => {
    setEditingSteps(prev => [
      ...prev,
      { order: prev.length + 1, action: 'click', selector: '', value: '', expected_result: '', description: '' },
    ])
  }

  const removeStep = (idx: number) => {
    setEditingSteps(prev => prev.filter((_, i) => i !== idx).map((s, i) => ({ ...s, order: i + 1 })))
  }

  const updateStep = (idx: number, field: string, val: string) => {
    setEditingSteps(prev => prev.map((s, i) => i === idx ? { ...s, [field]: val } : s))
  }

  if (loading) return <PageLoader />
  if (error || !tc) return <PageError message={error || 'Test case not found'} onRetry={loadCase} />

  const steps = tc.test_steps ?? []

  return (
    <div className="animate-fade-in">
      <PageHeader
        title={tc.title}
        description={tc.description}
        breadcrumbs={[
          { label: 'Test Suites', href: '/suites' },
          { label: 'Suite', href: `/suites/${suiteId}` },
          { label: tc.title },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              onClick={handleGenerate}
              loading={generating}
              variant={tc.status === 'generated' ? 'secondary' : 'primary'}
            >
              <Sparkles className="w-4 h-4" />
              {generating ? 'Generating...' : tc.status === 'generated' ? 'Re-generate Steps' : 'AI Generate Steps'}
            </Button>
            {steps.length > 0 && (
              <Button variant="secondary" onClick={() => setShowRunModal(true)}>
                <Play className="w-4 h-4" />
                Run Test
              </Button>
            )}
          </div>
        }
      />

      {/* Case Meta */}
      <div className="flex items-center gap-3 mb-6">
        <CaseStatusBadge status={tc.status} />
        <Badge variant="default">{tc.test_type}</Badge>
        <span className="text-xs text-surface-500">{steps.length} steps</span>
        {tc.generation_attempts > 0 && (
          <span className="text-xs text-surface-500">
            {tc.generation_attempts} generation attempt{tc.generation_attempts !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Generation Progress */}
      {generating && genStatus?.generation && (
        <Card className="mb-6 border-primary-800/50">
          <CardContent>
            <div className="flex items-center gap-3 mb-3">
              <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />
              <h3 className="text-sm font-semibold text-primary-300">AI Generation in Progress</h3>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {genStatus.generation.progress.map((msg, i) => (
                <div key={i} className="flex items-start gap-2 text-xs text-surface-400">
                  <span className="text-surface-600 mt-0.5">▸</span>
                  {msg}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-4 border-b border-surface-800">
        {['steps', 'code', 'runner'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab as any)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
              activeTab === tab
                ? 'border-primary-500 text-primary-400'
                : 'border-transparent text-surface-400 hover:text-surface-200'
            }`}
          >
            {tab === 'steps' && <span className="inline-flex items-center gap-1.5"><ListOrdered className="w-4 h-4" />Test Steps</span>}
            {tab === 'code' && <span className="inline-flex items-center gap-1.5"><Code2 className="w-4 h-4" />Generated Code</span>}
            {tab === 'runner' && <span className="inline-flex items-center gap-1.5"><Play className="w-4 h-4" />Live Runner</span>}
          </button>
        ))}
      </div>

      {/* Steps Tab */}
      {activeTab === 'steps' && (
        <div>
          {steps.length === 0 ? (
            <Card>
              <CardContent className="text-center py-12">
                <Sparkles className="w-10 h-10 text-surface-500 mx-auto mb-3" />
                <h3 className="text-base font-semibold text-surface-200 mb-1">No steps generated yet</h3>
                <p className="text-sm text-surface-400 mb-4">
                  Click "AI Generate Steps" to let the AI analyze your application and create test steps.
                </p>
                <Button onClick={handleGenerate} loading={generating}>
                  <Sparkles className="w-4 h-4" />
                  Generate Steps
                </Button>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex justify-end mb-3">
                <Button variant="secondary" size="sm" onClick={startEditSteps}>
                  Edit Steps
                </Button>
              </div>
              <div className="space-y-2">
                {steps.sort((a, b) => a.order - b.order).map((step, idx) => {
                  const Icon = actionIcons[step.action] ?? ListOrdered
                  return (
                    <Card key={step.id}>
                      <CardContent className="flex items-start gap-4">
                        <div className="flex items-center gap-3 flex-shrink-0">
                          <span className="w-7 h-7 rounded-full bg-surface-800 flex items-center justify-center text-xs font-bold text-surface-300">
                            {step.order}
                          </span>
                          <div className="w-8 h-8 rounded-lg bg-primary-600/10 flex items-center justify-center">
                            <Icon className="w-4 h-4 text-primary-400" />
                          </div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="info">{step.action}</Badge>
                            {step.description && (
                              <span className="text-sm text-surface-200">{step.description}</span>
                            )}
                          </div>
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-surface-400">
                            {step.selector && (
                              <span>
                                <span className="text-surface-500">Selector:</span>{' '}
                                <code className="text-amber-400/80 bg-surface-800 px-1.5 py-0.5 rounded">{step.selector}</code>
                              </span>
                            )}
                            {step.value && (
                              <span>
                                <span className="text-surface-500">Value:</span>{' '}
                                <code className="text-emerald-400/80 bg-surface-800 px-1.5 py-0.5 rounded">{step.value}</code>
                              </span>
                            )}
                            {step.expected_result && (
                              <span>
                                <span className="text-surface-500">Expected:</span>{' '}
                                <span className="text-surface-300">{step.expected_result}</span>
                              </span>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            </>
          )}
        </div>
      )}

      {/* Code Tab */}
      {activeTab === 'code' && (
        <Card>
          {code ? (
            <div className="relative">
              <div className="flex items-center justify-between px-5 pt-4 pb-2 border-b border-surface-800">
                <span className="text-xs text-surface-400 font-mono">{tc.title.toLowerCase().replace(/\s+/g, '_')}_suite.spec.ts</span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigator.clipboard.writeText(code)}
                  >
                    Copy
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleRegenerateCode}
                    loading={regeneratingCode}
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Regenerate
                  </Button>
                </div>
              </div>
              <pre className="p-5 text-sm text-surface-200 overflow-x-auto font-mono leading-relaxed whitespace-pre">
                {code}
              </pre>
            </div>
          ) : (
            <CardContent className="text-center py-12">
              <Code2 className="w-10 h-10 text-surface-500 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-surface-200 mb-1">No code generated</h3>
              <p className="text-sm text-surface-400 mb-4">Generate test steps first, then code will be auto-generated.</p>
              {steps.length > 0 && (
                <Button onClick={handleRegenerateCode} loading={regeneratingCode}>
                  <Sparkles className="w-4 h-4" />
                  Generate Code
                </Button>
              )}
            </CardContent>
          )}
        </Card>
      )}

      {/* Runner Tab */}
      {activeTab === 'runner' && (
        <div>
          {!activeRunId ? (
            <div className="flex flex-col items-center justify-center py-16 rounded-xl border border-surface-800 bg-surface-900">
              <div className="w-16 h-16 rounded-2xl bg-surface-800 flex items-center justify-center mb-4">
                <Play className="w-8 h-8 text-surface-500" />
              </div>
              <h3 className="text-base font-semibold text-surface-200 mb-1">No active run</h3>
              <p className="text-sm text-surface-400 mb-5">Start a test run to see live runner.</p>
              <Button onClick={() => setShowRunModal(true)}>
                <Play className="w-4 h-4" />
                Start Run
              </Button>

              {/* Recent Runs */}
              {recentRuns.length > 0 && (
                <div className="w-full max-w-md mt-8 border-t border-surface-800 pt-6">
                  <h4 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-3 text-center">Previous Runs</h4>
                  <div className="space-y-1">
                    {recentRuns.slice(0, 5).map(run => (
                      <div
                        key={run.id}
                        className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-surface-800 rounded-lg transition-colors"
                        onClick={() => navigate(`/runs/${run.id}`)}
                      >
                        <div className="flex items-center gap-3">
                          <RunStatusBadge status={run.status} />
                          <span className="text-sm text-surface-300">{run.browser}</span>
                        </div>
                        <span className="text-xs text-surface-500">
                          {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '—'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <TestRunner
              testTitle={tc.title}
              steps={steps}
              wsSteps={wsSteps}
              wsStatus={wsStatus}
              connected={wsConnected}
              runId={activeRunId}
              browser={runBrowser}
              baseUrl={baseUrl}
              onRerun={() => handleRunTest()}
            />
          )}
        </div>
      )}

      {/* Run Test Modal */}
      <Modal open={showRunModal} onClose={() => setShowRunModal(false)} title="Run Test" size="sm">
        <div className="space-y-4">
          <Select
            id="run-browser"
            label="Browser"
            options={[
              { value: 'chromium', label: 'Chromium' },
              { value: 'firefox', label: 'Firefox' },
              { value: 'webkit', label: 'WebKit (Safari)' },
            ]}
            value={runBrowser}
            onChange={e => setRunBrowser(e.target.value)}
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowRunModal(false)}>Cancel</Button>
            <Button onClick={handleRunTest} loading={creatingRun}>
              <Play className="w-4 h-4" />
              Start Run
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit Steps Modal */}
      <Modal open={showEditStep} onClose={() => setShowEditStep(false)} title="Edit Test Steps" size="lg">
        <div className="space-y-3 max-h-[60vh] overflow-y-auto">
          {editingSteps.map((step, idx) => (
            <div key={idx} className="flex items-start gap-2 p-3 bg-surface-800 rounded-lg">
              <span className="text-xs font-bold text-surface-400 mt-2.5 w-6 text-center">{idx + 1}</span>
              <div className="flex-1 grid grid-cols-2 gap-2">
                <Select
                  id={`step-action-${idx}`}
                  options={actionOptions}
                  value={step.action}
                  onChange={e => updateStep(idx, 'action', e.target.value)}
                />
                <Input
                  id={`step-selector-${idx}`}
                  placeholder="Selector"
                  value={step.selector ?? ''}
                  onChange={e => updateStep(idx, 'selector', e.target.value)}
                />
                <Input
                  id={`step-value-${idx}`}
                  placeholder="Value"
                  value={step.value ?? ''}
                  onChange={e => updateStep(idx, 'value', e.target.value)}
                />
                <Input
                  id={`step-desc-${idx}`}
                  placeholder="Description"
                  value={step.description ?? ''}
                  onChange={e => updateStep(idx, 'description', e.target.value)}
                />
              </div>
              <button
                onClick={() => removeStep(idx)}
                className="p-1.5 text-surface-500 hover:text-red-400 mt-1.5 cursor-pointer"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
          <Button variant="ghost" size="sm" onClick={addStep}>
            <Plus className="w-4 h-4" />
            Add Step
          </Button>
        </div>
        <div className="flex justify-end gap-3 pt-4 mt-4 border-t border-surface-800">
          <Button variant="secondary" onClick={() => setShowEditStep(false)}>Cancel</Button>
          <Button onClick={handleSaveSteps} loading={savingSteps}>Save Steps</Button>
        </div>
      </Modal>
    </div>
  )
}
