// ─── Test Suite ───
export interface TestSuite {
  id: string
  name: string
  description: string | null
  base_url: string
  app_description: string | null
  login_url: string | null
  login_username: string | null
  has_auth: boolean
  created_at: string
  updated_at: string
}

export interface TestSuiteDetail extends TestSuite {
  test_cases: TestCase[]
}

export interface CreateTestSuiteRequest {
  name: string
  description?: string
  base_url: string
  app_description?: string
  login_url?: string
  login_username?: string
  login_password?: string
}

export interface UpdateTestSuiteRequest {
  name?: string
  description?: string
  base_url?: string
  app_description?: string
  login_url?: string | null
  login_username?: string | null
  login_password?: string | null
}

// ─── Test Case ───
export type TestCaseStatus = 'draft' | 'generating' | 'generated' | 'failed'
export type TestType = 'functional' | 'e2e' | 'integration' | 'accessibility' | 'visual' | 'performance'

export interface TestCase {
  id: string
  suite_id: string
  title: string
  description: string
  test_type: string
  status: TestCaseStatus
  generation_attempts: number
  created_at: string
  updated_at: string
}

export interface TestStep {
  id: string
  case_id: string
  order: number
  action: string
  selector: string | null
  value: string | null
  expected_result: string | null
  description: string | null
  metadata_: Record<string, unknown> | null
  created_at: string
}

export interface TestCaseDetail extends TestCase {
  test_steps: TestStep[]
}

export interface CreateTestCaseRequest {
  title: string
  description: string
  test_type?: TestType
}

export interface UpdateTestStepRequest {
  order: number
  action: string
  selector?: string | null
  value?: string | null
  expected_result?: string | null
  description?: string | null
}

// ─── Test Run ───
export type RunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error'

export interface TestRun {
  id: string
  case_id: string
  status: RunStatus
  browser: string
  headed: boolean
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  error_message: string | null
  created_at: string
}

export interface Artifact {
  id: string
  run_id: string
  artifact_type: 'screenshot' | 'video' | 'trace' | 'log'
  file_name: string
  mime_type: string | null
  file_size: number | null
  created_at: string
}

export interface TestRunDetail extends TestRun {
  result_summary: {
    total: number
    passed: number
    failed: number
    skipped: number
    duration: number
  } | null
  artifacts: Artifact[]
  base_url?: string | null
}

export interface CreateTestRunRequest {
  case_id: string
  browser?: 'chromium' | 'firefox' | 'webkit'
  headed?: boolean
}

// ─── Generation ───
export interface GenerationStatus {
  case_id: string
  case_status: TestCaseStatus
  generation: {
    status: 'running' | 'success' | 'failed'
    progress: string[]
    error: string | null
    steps_count: number
    code_generated: boolean
    code_file: string | null
  } | null
}

export interface TestCode {
  case_id: string
  file_name: string
  code_content: string
}

// ─── Site Crawl ───
export interface CrawlPageResult {
  index: number
  url: string
  page_title: string | null
  element_count: number
  form_count: number
  file: string
  screenshot_file?: string | null
}

export interface CrawlManifest {
  suite_id: string
  base_url: string
  crawled_at: string
  total_pages: number
  total_elements: number
  pages: CrawlPageResult[]
}

export interface CrawlStatus {
  status: 'idle' | 'running' | 'completed' | 'failed'
  total_pages?: number
  total_elements?: number
  crawled_at?: string
  error: string | null
}

export interface WsCrawlPage {
  event: 'crawl_page'
  url: string
  page_title: string | null
  element_count: number
  form_count: number
  screenshot_base64: string | null
  pages_done: number
  pages_total: number
  timestamp?: string
}

export interface WsCrawlComplete {
  event: 'crawl_complete'
  total_pages: number
  total_elements: number
  timestamp?: string
}

export interface WsCrawlError {
  event: 'crawl_error'
  error: string
  timestamp?: string
}

export type WsCrawlMessage = WsCrawlPage | WsCrawlComplete | WsCrawlError

// ─── WebSocket Events ───
export interface WsStatusChange {
  event: 'status_change'
  status: RunStatus
  timestamp: string
}

export interface WsTestStep {
  event: 'test_step'
  step: string
  status: 'passed' | 'failed'
  order: number
  action: string
  value?: string | null
  duration_ms: number
  screenshot_base64?: string
  timestamp: string
}

export interface WsArtifactReady {
  event: 'artifact_ready'
  artifact: Artifact
  timestamp: string
}

export type WsMessage = WsStatusChange | WsTestStep | WsArtifactReady
