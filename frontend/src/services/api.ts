import axios from 'axios'
import type {
  TestSuite,
  TestSuiteDetail,
  CreateTestSuiteRequest,
  UpdateTestSuiteRequest,
  TestCase,
  TestCaseDetail,
  CreateTestCaseRequest,
  UpdateTestStepRequest,
  TestRun,
  TestRunDetail,
  CreateTestRunRequest,
  GenerationStatus,
  TestCode,
  CrawlStatus,
  CrawlManifest,
} from '../types'

const api = axios.create({
  baseURL: '/api',
})

// ─── Test Suites ───
export const suiteApi = {
  list: () => api.get<TestSuite[]>('/test-suites').then(r => r.data),
  get: (id: string) => api.get<TestSuiteDetail>(`/test-suites/${id}`).then(r => r.data),
  create: (data: CreateTestSuiteRequest) => api.post<TestSuite>('/test-suites', data).then(r => r.data),
  update: (id: string, data: UpdateTestSuiteRequest) => api.patch<TestSuite>(`/test-suites/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/test-suites/${id}`),
}

// ─── Test Cases ───
export const caseApi = {
  listBySuite: (suiteId: string) => api.get<TestCase[]>(`/test-suites/${suiteId}/test-cases`).then(r => r.data),
  get: (caseId: string) => api.get<TestCaseDetail>(`/test-cases/${caseId}`).then(r => r.data),
  create: (suiteId: string, data: CreateTestCaseRequest) =>
    api.post<TestCase>(`/test-suites/${suiteId}/test-cases`, data).then(r => r.data),
  delete: (caseId: string) => api.delete(`/test-cases/${caseId}`),
  updateSteps: (caseId: string, steps: UpdateTestStepRequest[]) =>
    api.put<TestCaseDetail>(`/test-cases/${caseId}/steps`, { steps }).then(r => r.data),
}

// ─── Generation ───
export const generationApi = {
  trigger: (caseId: string) => api.post(`/test-cases/${caseId}/generate`).then(r => r.data),
  status: (caseId: string) => api.get<GenerationStatus>(`/test-cases/${caseId}/generate/status`).then(r => r.data),
  getCode: (caseId: string) => api.get<TestCode>(`/test-cases/${caseId}/code`).then(r => r.data),
  regenerateCode: (caseId: string) => api.post(`/test-cases/${caseId}/code/generate`).then(r => r.data),
}

// ─── Settings ───
export const settingsApi = {
  get: () => api.get<{
    ollama_model: string
    llm_temperature: number
    ollama_base_url: string
    step_timeout_ms: number
    navigation_timeout_ms: number
    execution_timeout_s: number
    max_reverification_attempts: number
  }>('/settings').then(r => r.data),
}

// ─── Test Runs ───
export const runApi = {
  list: (params?: { case_id?: string; status_filter?: string }) =>
    api.get<TestRun[]>('/test-runs', { params }).then(r => r.data),
  get: (runId: string) => api.get<TestRunDetail>(`/test-runs/${runId}`).then(r => r.data),
  create: (data: CreateTestRunRequest) => api.post<TestRun>('/test-runs', data).then(r => r.data),
  delete: (runId: string) => api.delete(`/test-runs/${runId}`),
  downloadArtifact: (runId: string, artifactId: string) =>
    `/api/test-runs/${runId}/artifacts/${artifactId}/download`,
}

// ─── Site Crawl ───
export const crawlApi = {
  trigger: (suiteId: string) =>
    api.post<{ status: string; suite_id: string }>(`/test-suites/${suiteId}/crawl`).then(r => r.data),
  status: (suiteId: string) =>
    api.get<CrawlStatus>(`/test-suites/${suiteId}/crawl/status`).then(r => r.data),
  results: (suiteId: string) =>
    api.get<CrawlManifest>(`/test-suites/${suiteId}/crawl/results`).then(r => r.data),
  page: (suiteId: string, pageIndex: number) =>
    api.get(`/test-suites/${suiteId}/crawl/pages/${pageIndex}`).then(r => r.data),
}
