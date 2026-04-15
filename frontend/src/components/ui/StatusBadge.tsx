import type { RunStatus, TestCaseStatus } from '../../types'
import { Badge } from './Badge'

const runStatusMap: Record<RunStatus, { label: string; variant: 'success' | 'warning' | 'danger' | 'info' | 'muted' }> = {
  pending: { label: 'Pending', variant: 'muted' },
  running: { label: 'Running', variant: 'info' },
  passed: { label: 'Passed', variant: 'success' },
  failed: { label: 'Failed', variant: 'danger' },
  error: { label: 'Error', variant: 'danger' },
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const cfg = runStatusMap[status] ?? { label: status, variant: 'muted' as const }
  return (
    <Badge variant={cfg.variant} dot>
      {cfg.label}
    </Badge>
  )
}

const caseStatusMap: Record<TestCaseStatus, { label: string; variant: 'success' | 'warning' | 'danger' | 'info' | 'muted' }> = {
  draft: { label: 'Draft', variant: 'muted' },
  generating: { label: 'Generating', variant: 'info' },
  generated: { label: 'Generated', variant: 'success' },
  failed: { label: 'Failed', variant: 'danger' },
}

export function CaseStatusBadge({ status }: { status: TestCaseStatus }) {
  const cfg = caseStatusMap[status] ?? { label: status, variant: 'muted' as const }
  return (
    <Badge variant={cfg.variant} dot>
      {cfg.label}
    </Badge>
  )
}
