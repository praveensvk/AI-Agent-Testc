import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Plus, FileCheck2, Trash2, Sparkles, Globe, Lock, Pencil, ShieldOff, Radar } from 'lucide-react'
import { Card, CardContent } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { Input, Textarea, Select } from '../components/ui/FormFields'
import { CaseStatusBadge } from '../components/ui/StatusBadge'
import { Badge } from '../components/ui/Badge'
import { EmptyState, PageLoader, PageError } from '../components/ui/EmptyState'
import { suiteApi, caseApi, crawlApi } from '../services/api'
import { useCrawlSocket } from '../hooks/useCrawlSocket'
import { CrawlRunner } from '../components/crawler/CrawlRunner'
import { CrawlResultsPanel } from '../components/crawler/CrawlResultsPanel'
import type { TestSuiteDetail, CreateTestCaseRequest, UpdateTestSuiteRequest, TestType, CrawlManifest } from '../types'
import { formatDistanceToNow } from 'date-fns'

const testTypes: { value: TestType; label: string }[] = [
  { value: 'functional', label: 'Functional' },
  { value: 'e2e', label: 'End-to-End' },
  { value: 'integration', label: 'Integration' },
  { value: 'accessibility', label: 'Accessibility' },
  { value: 'visual', label: 'Visual' },
  { value: 'performance', label: 'Performance' },
]

export function SuiteDetailPage() {
  const { suiteId } = useParams<{ suiteId: string }>()
  const navigate = useNavigate()
  const [suite, setSuite] = useState<TestSuiteDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<CreateTestCaseRequest>({
    title: '',
    description: '',
    test_type: 'functional',
  })

  // Crawl state
  const [showCrawl, setShowCrawl] = useState(false)
  const [crawlStarting, setCrawlStarting] = useState(false)
  const [existingCrawl, setExistingCrawl] = useState<CrawlManifest | null>(null)
  const crawl = useCrawlSocket(suiteId ?? null)

  // Auth editing state
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [savingAuth, setSavingAuth] = useState(false)
  const [authForm, setAuthForm] = useState<UpdateTestSuiteRequest>({
    login_url: '',
    login_username: '',
    login_password: '',
  })

  const loadSuite = () => {
    if (!suiteId) return
    setLoading(true)
    setError(null)
    suiteApi.get(suiteId)
      .then(setSuite)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadSuite() }, [suiteId])

  useEffect(() => {
    if (!suiteId) return
    crawlApi.results(suiteId)
      .then(data => setExistingCrawl(data))
      .catch(() => setExistingCrawl(null))
  }, [suiteId])

  const handleAutoGen = async () => {
    if (!suiteId) return
    crawl.reset()
    // Connect to WebSocket FIRST so we don't miss early events
    crawl.connect()
    setCrawlStarting(true)
    setShowCrawl(true)
    setExistingCrawl(null) // hide results panel while new crawl runs
    try {
      await crawlApi.trigger(suiteId)
    } catch {
      // 409 = already running, WS is already connected so events will still arrive
    } finally {
      setCrawlStarting(false)
    }
  }

  // When crawl completes, refresh manifest so CrawlResultsPanel takes over
  useEffect(() => {
    if (crawl.status === 'completed' && suiteId) {
      crawlApi.results(suiteId)
        .then(data => {
          setExistingCrawl(data)
          setShowCrawl(false)
          crawl.disconnect()
        })
        .catch(() => {})
    }
  }, [crawl.status, suiteId])

  const handleCreateCase = async () => {
    if (!suiteId || !form.title.trim() || !form.description.trim()) return
    setCreating(true)
    try {
      await caseApi.create(suiteId, form)
      setShowCreate(false)
      setForm({ title: '', description: '', test_type: 'functional' })
      loadSuite()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteCase = async (e: React.MouseEvent, caseId: string) => {
    e.stopPropagation()
    if (!confirm('Delete this test case?')) return
    try {
      await caseApi.delete(caseId)
      loadSuite()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const openAuthModal = () => {
    setAuthForm({
      login_url: suite?.login_url || '',
      login_username: suite?.login_username || '',
      login_password: '',
    })
    setShowAuthModal(true)
  }

  const handleSaveAuth = async () => {
    if (!suiteId) return
    setSavingAuth(true)
    try {
      const payload: UpdateTestSuiteRequest = {
        login_url: authForm.login_url,
        login_username: authForm.login_username,
      }
      // Only send password if user typed a new one
      if (authForm.login_password) {
        payload.login_password = authForm.login_password
      }
      await suiteApi.update(suiteId, payload)
      setShowAuthModal(false)
      loadSuite()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSavingAuth(false)
    }
  }

  const handleRemoveAuth = async () => {
    if (!suiteId || !confirm('Remove authentication from this suite?')) return
    setSavingAuth(true)
    try {
      await suiteApi.update(suiteId, {
        login_url: null,
        login_username: null,
        login_password: null,
      })
      setShowAuthModal(false)
      loadSuite()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSavingAuth(false)
    }
  }

  if (loading) return <PageLoader />
  if (error || !suite) return <PageError message={error || 'Suite not found'} onRetry={loadSuite} />

  const cases = suite.test_cases ?? []

  return (
    <div className="animate-fade-in">
      <PageHeader
        title={suite.name}
        description={suite.description || undefined}
        breadcrumbs={[
          { label: 'Test Suites', href: '/suites' },
          { label: suite.name },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={handleAutoGen} loading={crawlStarting}>
              <Radar className="w-4 h-4" />
              Auto-Gen
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="w-4 h-4" />
              Add Test Case
            </Button>
          </div>
        }
      />

      {/* Crawl Runner — shown only during an active live crawl */}
      {showCrawl && suite && (
        <div className="mb-6">
          <CrawlRunner
            suiteId={suiteId!}
            suiteName={suite.name}
            baseUrl={suite.base_url}
            pages={crawl.pages}
            status={crawl.status}
            connected={crawl.connected}
            latestScreenshot={crawl.latestScreenshot}
            summary={crawl.summary}
            errorMsg={crawl.errorMsg}
            onDismiss={() => { setShowCrawl(false); crawl.disconnect() }}
          />
        </div>
      )}

      {/* Crawl Results Panel — shown when crawl data exists and no active crawl */}
      {!showCrawl && existingCrawl && suiteId && (
        <CrawlResultsPanel
          suiteId={suiteId}
          manifest={existingCrawl}
          onRerun={handleAutoGen}
        />
      )}

      {/* Suite Info */}
      <Card className="mb-6">
        <CardContent className="flex flex-wrap gap-6">
          <div className="flex items-center gap-2 text-sm text-surface-400">
            <Globe className="w-4 h-4" />
            <a
              href={suite.base_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-400 hover:text-primary-300 transition-colors"
            >
              {suite.base_url}
            </a>
          </div>
          {suite.has_auth ? (
            <div className="flex items-center gap-1.5 text-sm">
              <Lock className="w-3.5 h-3.5 text-primary-400" />
              <span className="text-primary-400 font-medium text-xs">Authenticated</span>
              {suite.login_username && (
                <span className="text-surface-500 text-xs">({suite.login_username})</span>
              )}
              <button
                onClick={openAuthModal}
                className="ml-1 p-1 rounded text-surface-500 hover:text-primary-400 hover:bg-primary-500/10 transition-colors cursor-pointer"
                title="Edit authentication"
              >
                <Pencil className="w-3 h-3" />
              </button>
            </div>
          ) : (
            <button
              onClick={openAuthModal}
              className="flex items-center gap-1.5 text-sm text-surface-500 hover:text-primary-400 transition-colors cursor-pointer"
              title="Add authentication"
            >
              <Lock className="w-3.5 h-3.5" />
              <span className="text-xs">Add Auth</span>
            </button>
          )}
          <div className="flex items-center gap-2 text-sm text-surface-400">
            <FileCheck2 className="w-4 h-4" />
            {cases.length} test case{cases.length !== 1 ? 's' : ''}
          </div>
          {suite.app_description && (
            <p className="text-sm text-surface-400 w-full">{suite.app_description}</p>
          )}
        </CardContent>
      </Card>

      {/* Test Cases List */}
      {cases.length === 0 ? (
        <EmptyState
          icon={FileCheck2}
          title="No test cases"
          description="Add a test case and let AI generate executable test steps automatically."
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="w-4 h-4" />
              Add Test Case
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {cases.map(tc => (
            <Card
              key={tc.id}
              hover
              onClick={() => navigate(`/suites/${suiteId}/cases/${tc.id}`)}
            >
              <CardContent className="flex items-center justify-between">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-10 h-10 rounded-lg bg-surface-800 flex items-center justify-center flex-shrink-0">
                    <FileCheck2 className="w-5 h-5 text-surface-400" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-medium text-surface-100 truncate">
                        {tc.title}
                      </h3>
                      <CaseStatusBadge status={tc.status} />
                      <Badge variant="default">{tc.test_type}</Badge>
                    </div>
                    <p className="text-xs text-surface-500 truncate mt-0.5">{tc.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  {tc.status === 'draft' && (
                    <div className="flex items-center gap-1 text-xs text-primary-400">
                      <Sparkles className="w-3 h-3" />
                      Generate
                    </div>
                  )}
                  <span className="text-xs text-surface-500">
                    {formatDistanceToNow(new Date(tc.updated_at), { addSuffix: true })}
                  </span>
                  <button
                    onClick={(e) => handleDeleteCase(e, tc.id)}
                    className="p-1.5 rounded-lg text-surface-500 hover:text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Test Case Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Add Test Case" size="md">
        <div className="space-y-4">
          <Input
            id="case-title"
            label="Test Title"
            placeholder="e.g. Verify user can login with valid credentials"
            value={form.title}
            onChange={e => setForm(prev => ({ ...prev, title: e.target.value }))}
          />
          <Textarea
            id="case-desc"
            label="Description (Natural Language)"
            placeholder="Describe what should be tested. AI will generate test steps from this.&#10;&#10;Example: Navigate to login, enter email and password, click login, verify dashboard loads."
            rows={4}
            value={form.description}
            onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
          />
          <Select
            id="case-type"
            label="Test Type"
            options={testTypes}
            value={form.test_type}
            onChange={e => setForm(prev => ({ ...prev, test_type: e.target.value as TestType }))}
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button
              onClick={handleCreateCase}
              loading={creating}
              disabled={!form.title.trim() || !form.description.trim()}
            >
              <Sparkles className="w-4 h-4" />
              Create Test Case
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit Authentication Modal */}
      <Modal open={showAuthModal} onClose={() => setShowAuthModal(false)} title="Suite Authentication" size="md">
        <div className="space-y-4">
          <p className="text-xs text-surface-500">
            Provide login credentials if the app requires authentication to access pages. These are used during crawling and test generation.
          </p>
          <Input
            id="auth-login-url"
            label="Login URL"
            placeholder="https://example.com/login"
            value={authForm.login_url ?? ''}
            onChange={e => setAuthForm(prev => ({ ...prev, login_url: e.target.value }))}
          />
          <Input
            id="auth-login-username"
            label="Username / Email"
            placeholder="testuser@example.com"
            value={authForm.login_username ?? ''}
            onChange={e => setAuthForm(prev => ({ ...prev, login_username: e.target.value }))}
          />
          <Input
            id="auth-login-password"
            label="Password"
            placeholder={suite?.has_auth ? '••••••••  (leave blank to keep current)' : '••••••••'}
            type="password"
            value={authForm.login_password ?? ''}
            onChange={e => setAuthForm(prev => ({ ...prev, login_password: e.target.value }))}
          />
          <div className="flex items-center justify-between pt-2">
            <div>
              {suite?.has_auth && (
                <Button variant="secondary" onClick={handleRemoveAuth} loading={savingAuth}>
                  <ShieldOff className="w-4 h-4" />
                  Remove Auth
                </Button>
              )}
            </div>
            <div className="flex gap-3">
              <Button variant="secondary" onClick={() => setShowAuthModal(false)}>Cancel</Button>
              <Button
                onClick={handleSaveAuth}
                loading={savingAuth}
                disabled={!authForm.login_url?.trim() || !authForm.login_username?.trim()}
              >
                <Lock className="w-4 h-4" />
                Save Authentication
              </Button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
