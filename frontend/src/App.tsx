import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { DashboardPage } from './pages/DashboardPage'
import { SuitesPage } from './pages/SuitesPage'
import { SuiteDetailPage } from './pages/SuiteDetailPage'
import { CaseDetailPage } from './pages/CaseDetailPage'
import { TestRunsPage } from './pages/TestRunsPage'
import { RunDetailPage } from './pages/RunDetailPage'
import { ReportsPage } from './pages/ReportsPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/suites" element={<SuitesPage />} />
        <Route path="/suites/:suiteId" element={<SuiteDetailPage />} />
        <Route path="/suites/:suiteId/cases/:caseId" element={<CaseDetailPage />} />
        <Route path="/runs" element={<TestRunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
