import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Play,
  Square,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  Monitor,
  Globe,
  Mouse,
  Type,
  Eye,
  Camera,
  ArrowDown,
  ChevronDown,
  ChevronRight,
  Wifi,
  WifiOff,
  Maximize2,
  ExternalLink,
  ListOrdered,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { TestStep, WsTestStep, TestRun } from '../../types'

// ─── Action icon mapping ───
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

// ─── Action color mapping (Cypress-like command colors) ───
const actionColors: Record<string, string> = {
  navigate: 'text-cyan-400',
  click: 'text-blue-400',
  type: 'text-violet-400',
  fill: 'text-violet-400',
  verify_text: 'text-emerald-400',
  verify_element: 'text-emerald-400',
  wait: 'text-amber-400',
  screenshot: 'text-pink-400',
  scroll: 'text-orange-400',
  hover: 'text-blue-400',
  press: 'text-violet-400',
  select: 'text-blue-400',
  clear: 'text-surface-400',
}

interface TestRunnerProps {
  testTitle: string
  steps: TestStep[]
  wsSteps: WsTestStep[]
  wsStatus: string | null
  connected: boolean
  runId: string | null
  browser: string
  baseUrl?: string
  onRerun?: () => void
  onStop?: () => void
}

export function TestRunner({
  testTitle,
  steps,
  wsSteps,
  wsStatus,
  connected,
  runId,
  browser,
  baseUrl,
  onRerun,
  onStop,
}: TestRunnerProps) {
  const navigate = useNavigate()
  const [hoveredStep, setHoveredStep] = useState<number | null>(null)
  const [pinnedStep, setPinnedStep] = useState<number | null>(null)
  const [isTestExpanded, setIsTestExpanded] = useState(true)
  const commandLogRef = useRef<HTMLDivElement>(null)

  // "running" only if the WS is actually open; once it closes the status
  // must be resolved from a terminal value (passed/failed/error) or idle.
  const isRunning = connected && (wsStatus === null || wsStatus === 'running')
  const isPassed = wsStatus === 'passed'
  const isFailed = wsStatus === 'failed' || wsStatus === 'error'
  const isComplete = isPassed || isFailed

  // Compute stats
  const passedCount = wsSteps.filter(s => s.status === 'passed').length
  const failedCount = wsSteps.filter(s => s.status === 'failed').length
  const totalDuration = wsSteps.reduce((sum, s) => sum + (s.duration_ms || 0), 0)
  // Only count WS messages that represent real steps (have an order) as "completed"
  const completedStepCount = wsSteps.filter(s => s.order != null).length
  const remainingCount = Math.max(0, steps.length - completedStepCount)

  // Get the preview screenshot (pinned > hovered > last completed step)
  const activeStepOrder = pinnedStep ?? hoveredStep
  const previewStep = activeStepOrder
    ? wsSteps.find(w => w.order === activeStepOrder)
    : wsSteps[wsSteps.length - 1]

  // Find current URL from steps
  const getCurrentUrl = () => {
    const navSteps = wsSteps.filter(s => s.action === 'navigate')
    if (activeStepOrder) {
      const relevantNav = [...wsSteps]
        .filter(s => s.action === 'navigate' && s.order <= activeStepOrder)
        .pop()
      return relevantNav ? extractUrl(relevantNav) : baseUrl
    }
    return navSteps.length > 0 ? extractUrl(navSteps[navSteps.length - 1]) : baseUrl
  }

  const extractUrl = (step: WsTestStep) => {
    // The step description or value might contain the URL
    const match = step.step?.match(/https?:\/\/[^\s"']+/)
    return match?.[0] ?? baseUrl
  }

  // Auto-scroll command log to bottom during running
  useEffect(() => {
    if (isRunning && commandLogRef.current && !hoveredStep && !pinnedStep) {
      commandLogRef.current.scrollTop = commandLogRef.current.scrollHeight
    }
  }, [wsSteps.length, isRunning, hoveredStep, pinnedStep])

  const currentUrl = getCurrentUrl()

  return (
    <div className="flex flex-col h-[calc(100vh-220px)] min-h-[500px] rounded-xl border border-surface-800 overflow-hidden bg-surface-950">
      {/* ═══ Top Toolbar ═══ */}
      <div className="flex items-center justify-between h-10 px-3 bg-surface-900 border-b border-surface-800 flex-shrink-0">
        <div className="flex items-center gap-2">
          {/* Run status indicator */}
          <div className={clsx(
            'w-2 h-2 rounded-full',
            isRunning && 'bg-blue-400 animate-pulse-dot',
            isPassed && 'bg-emerald-400',
            isFailed && 'bg-red-400',
          )} />
          <span className="text-xs font-medium text-surface-300 truncate max-w-[200px]">
            {testTitle}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {/* Stats pills */}
          {wsSteps.length > 0 && (
            <div className="flex items-center gap-3 mr-3">
              {passedCount > 0 && (
                <span className="flex items-center gap-1 text-xs text-emerald-400">
                  <CheckCircle2 className="w-3 h-3" />{passedCount}
                </span>
              )}
              {failedCount > 0 && (
                <span className="flex items-center gap-1 text-xs text-red-400">
                  <XCircle className="w-3 h-3" />{failedCount}
                </span>
              )}
              {totalDuration > 0 && (
                <span className="flex items-center gap-1 text-xs text-surface-400">
                  <Clock className="w-3 h-3" />{(totalDuration / 1000).toFixed(1)}s
                </span>
              )}
            </div>
          )}
          {/* Browser badge */}
          <div className="flex items-center gap-1 px-2 py-0.5 bg-surface-800 rounded text-xs text-surface-400">
            <Monitor className="w-3 h-3" />
            {browser}
          </div>
          {/* Connection indicator */}
          <div className={clsx(
            'ml-1 p-1 rounded',
            connected ? 'text-emerald-400' : 'text-surface-600'
          )}>
            {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          </div>
          {/* Controls */}
          {isRunning && onStop && (
            <button
              onClick={onStop}
              className="p-1 rounded text-surface-400 hover:text-red-400 hover:bg-surface-800 transition-colors cursor-pointer"
              title="Stop (s)"
            >
              <Square className="w-3.5 h-3.5" />
            </button>
          )}
          {isComplete && onRerun && (
            <button
              onClick={onRerun}
              className="p-1 rounded text-surface-400 hover:text-primary-400 hover:bg-surface-800 transition-colors cursor-pointer"
              title="Rerun (r)"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}
          {isComplete && runId && (
            <button
              onClick={() => navigate(`/runs/${runId}`)}
              className="p-1 rounded text-surface-400 hover:text-primary-400 hover:bg-surface-800 transition-colors cursor-pointer"
              title="View full report"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ═══ Main Split Panel ═══ */}
      <div className="flex flex-1 min-h-0">
        {/* ─── Left: Command Log ─── */}
        <div className="w-[420px] flex-shrink-0 flex flex-col border-r border-surface-800 bg-surface-900">
          {/* Test header (collapsible, like Cypress test name bar) */}
          <button
            onClick={() => setIsTestExpanded(!isTestExpanded)}
            className={clsx(
              'flex items-center gap-2 px-3 py-2 text-left w-full border-b border-surface-800',
              'hover:bg-surface-800/50 transition-colors cursor-pointer',
              isComplete && isPassed && 'bg-emerald-500/5',
              isComplete && isFailed && 'bg-red-500/5',
            )}
          >
            {isPassed ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            ) : isFailed ? (
              <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            ) : (
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />
            )}
            {isTestExpanded ? (
              <ChevronDown className="w-3 h-3 text-surface-500 flex-shrink-0" />
            ) : (
              <ChevronRight className="w-3 h-3 text-surface-500 flex-shrink-0" />
            )}
            <span className="text-xs font-semibold text-surface-200 truncate flex-1">
              {testTitle}
            </span>
            <span className="text-[10px] text-surface-500">
              {wsSteps.length}/{steps.length}
            </span>
          </button>

          {/* Command list */}
          <div
            ref={commandLogRef}
            className={clsx(
              'flex-1 overflow-y-auto',
              !isTestExpanded && 'hidden'
            )}
          >
            {steps.sort((a, b) => a.order - b.order).map(step => {
              const wsStep = wsSteps.find(w => w.order === step.order)
              const Icon = actionIcons[step.action] ?? ListOrdered
              const color = actionColors[step.action] ?? 'text-surface-400'
              const isActive = (pinnedStep ?? hoveredStep) === step.order
              const isCurrentlyRunning = !wsStep && wsSteps.length === step.order - 1 && isRunning
              const isPending = !wsStep && !isCurrentlyRunning

              // Insert a page event before navigate steps
              const showPageEvent = step.action === 'navigate' && wsStep

              return (
                <div key={step.id}>
                  {/* Page event marker (like Cypress) */}
                  {showPageEvent && (
                    <div className="flex items-center gap-2 px-3 py-1 bg-surface-950/50">
                      <div className="flex-1 h-px bg-surface-800" />
                      <span className="text-[10px] text-surface-600 uppercase tracking-wider font-medium">
                        page load
                      </span>
                      <div className="flex-1 h-px bg-surface-800" />
                    </div>
                  )}

                  {/* Command entry */}
                  <div
                    onMouseEnter={() => !pinnedStep && setHoveredStep(step.order)}
                    onMouseLeave={() => !pinnedStep && setHoveredStep(null)}
                    onClick={() => {
                      if (wsStep) {
                        setPinnedStep(prev => prev === step.order ? null : step.order)
                      }
                    }}
                    className={clsx(
                      'group flex items-center gap-2 px-3 py-1.5 transition-all duration-100 cursor-pointer',
                      'border-l-2',
                      // Status-based left border
                      wsStep?.status === 'passed' && 'border-l-emerald-500/50',
                      wsStep?.status === 'failed' && 'border-l-red-500/50',
                      isCurrentlyRunning && 'border-l-blue-500/50',
                      isPending && 'border-l-transparent',
                      // Hover/active bg
                      isActive && wsStep?.status === 'passed' && 'bg-emerald-500/8',
                      isActive && wsStep?.status === 'failed' && 'bg-red-500/8',
                      isActive && !wsStep && 'bg-surface-800/50',
                      !isActive && 'hover:bg-surface-800/30',
                      // Pinned indicator
                      pinnedStep === step.order && 'ring-1 ring-inset ring-primary-500/30',
                    )}
                  >
                    {/* Step number */}
                    <span className={clsx(
                      'w-5 text-right text-[10px] font-mono flex-shrink-0',
                      wsStep?.status === 'passed' && 'text-emerald-500/60',
                      wsStep?.status === 'failed' && 'text-red-500/60',
                      isCurrentlyRunning && 'text-blue-400/60',
                      isPending && 'text-surface-600',
                    )}>
                      {step.order}
                    </span>

                    {/* Status icon */}
                    <div className="w-4 flex-shrink-0 flex items-center justify-center">
                      {wsStep?.status === 'passed' ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : wsStep?.status === 'failed' ? (
                        <XCircle className="w-3.5 h-3.5 text-red-400" />
                      ) : isCurrentlyRunning ? (
                        <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
                      ) : (
                        <div className="w-1.5 h-1.5 rounded-full bg-surface-700" />
                      )}
                    </div>

                    {/* Action name (Cypress-style uppercase command) */}
                    <span className={clsx(
                      'text-[11px] font-bold uppercase tracking-wide flex-shrink-0 min-w-[70px]',
                      wsStep ? color : isCurrentlyRunning ? 'text-blue-400' : 'text-surface-600',
                    )}>
                      {step.action.replace('_', ' ')}
                    </span>

                    {/* Arguments / description */}
                    <span className={clsx(
                      'text-xs truncate flex-1 min-w-0',
                      wsStep ? 'text-surface-300' : 'text-surface-600',
                    )}>
                      {step.action === 'navigate'
                        ? step.value || step.selector || ''
                        : step.selector
                          ? step.selector
                          : step.description || step.value || ''
                      }
                    </span>

                    {/* Duration (right side, like Cypress) */}
                    {wsStep && (
                      <span className={clsx(
                        'text-[10px] font-mono flex-shrink-0 tabular-nums',
                        wsStep.duration_ms > 1000 ? 'text-amber-400/80' :
                        wsStep.duration_ms > 3000 ? 'text-red-400/80' :
                        'text-surface-500',
                      )}>
                        {wsStep.duration_ms}ms
                      </span>
                    )}
                  </div>

                  {/* Inline error for failed step */}
                  {wsStep?.status === 'failed' && (
                    <div className="mx-3 mb-1 ml-9 p-2 bg-red-500/8 border border-red-800/30 rounded text-xs">
                      <div className="flex items-center gap-1.5 text-red-400 font-semibold mb-1">
                        <XCircle className="w-3 h-3" />
                        AssertionError
                      </div>
                      <p className="text-red-300/80 text-[11px] leading-relaxed">
                        Step failed: {step.action} {step.selector && `on "${step.selector}"`}
                        {step.expected_result && ` — expected: ${step.expected_result}`}
                      </p>
                    </div>
                  )}
                </div>
              )
            })}

            {/* Completion summary bar */}
            {isComplete && (
              <div className={clsx(
                'mx-3 my-2 p-2 rounded text-xs text-center',
                isPassed && 'bg-emerald-500/10 text-emerald-400',
                isFailed && 'bg-red-500/10 text-red-400',
              )}>
                {isPassed
                  ? `✓ All ${passedCount} steps passed in ${(totalDuration / 1000).toFixed(1)}s`
                  : `✗ ${failedCount} of ${wsSteps.length} steps failed`
                }
              </div>
            )}
          </div>
        </div>

        {/* ─── Right: Preview Pane ─── */}
        <div className="flex-1 flex flex-col min-w-0 bg-surface-950">
          {/* URL bar */}
          <div className="flex items-center gap-2 h-9 px-3 bg-surface-900/60 border-b border-surface-800 flex-shrink-0">
            <Globe className="w-3.5 h-3.5 text-surface-500 flex-shrink-0" />
            <span className="text-xs text-surface-400 font-mono truncate flex-1">
              {currentUrl || 'about:blank'}
            </span>
            {pinnedStep && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary-500/15 text-primary-400 font-medium">
                📌 Step {pinnedStep}
              </span>
            )}
            {hoveredStep && !pinnedStep && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-800 text-surface-400 font-medium">
                Previewing Step {hoveredStep}
              </span>
            )}
          </div>

          {/* Screenshot / App preview */}
          <div className="flex-1 flex items-center justify-center p-4 relative overflow-hidden">
            {previewStep?.screenshot_base64 ? (
              <div className="relative w-full h-full flex items-center justify-center">
                <img
                  src={previewStep.screenshot_base64}
                  alt={`Step ${previewStep.order} preview`}
                  className="max-w-full max-h-full rounded-lg shadow-2xl border border-surface-800 object-contain"
                />
                {/* Viewport overlay info */}
                <div className="absolute top-2 right-2 px-2 py-1 bg-surface-900/90 rounded text-[10px] text-surface-500 backdrop-blur-sm">
                  1280 × 720
                </div>
                {/* Click indicator for click actions */}
                {previewStep.action === 'click' && (
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
                    <div className="w-4 h-4 rounded-full bg-red-500/60 ring-4 ring-red-500/20 animate-ping" />
                  </div>
                )}
              </div>
            ) : isRunning && wsSteps.length === 0 ? (
              <div className="flex flex-col items-center gap-4 text-center">
                <div className="relative">
                  <div className="w-16 h-16 rounded-2xl bg-surface-800 flex items-center justify-center">
                    <Monitor className="w-8 h-8 text-surface-500" />
                  </div>
                  <Loader2 className="absolute -bottom-1 -right-1 w-5 h-5 text-blue-400 animate-spin" />
                </div>
                <div>
                  <p className="text-sm font-medium text-surface-300">Launching browser...</p>
                  <p className="text-xs text-surface-500 mt-1">Starting {browser} and navigating to the target</p>
                </div>
              </div>
            ) : isRunning ? (
              <div className="flex flex-col items-center gap-4 text-center">
                <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
                <p className="text-sm text-surface-400">Executing step {wsSteps.length + 1}...</p>
              </div>
            ) : !isComplete ? (
              <div className="flex flex-col items-center gap-3 text-center">
                <div className="w-16 h-16 rounded-2xl bg-surface-800 flex items-center justify-center">
                  <Play className="w-8 h-8 text-surface-500" />
                </div>
                <p className="text-sm text-surface-400">Application preview will appear here</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 text-center">
                {isPassed ? (
                  <>
                    <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center">
                      <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                    </div>
                    <p className="text-sm font-medium text-emerald-400">All tests passed</p>
                    <p className="text-xs text-surface-400">Hover over a command to preview the snapshot</p>
                  </>
                ) : (
                  <>
                    <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center">
                      <XCircle className="w-8 h-8 text-red-400" />
                    </div>
                    <p className="text-sm font-medium text-red-400">Test failed</p>
                    <p className="text-xs text-surface-400">Click on a failed step to inspect the snapshot</p>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ═══ Bottom Status Bar ═══ */}
      <div className="flex items-center justify-between h-7 px-3 bg-surface-900 border-t border-surface-800 flex-shrink-0">
        <div className="flex items-center gap-3">
          <span className={clsx(
            'text-[10px] font-medium uppercase tracking-wider',
            isRunning && 'text-blue-400',
            isPassed && 'text-emerald-400',
            isFailed && 'text-red-400',
          )}>
            {isRunning ? 'Running' : isPassed ? 'Passed' : isFailed ? 'Failed' : 'Idle'}
          </span>
          {wsSteps.length > 0 && (
            <span className="text-[10px] text-surface-500">
              {passedCount} passed · {failedCount} failed · {remainingCount} remaining
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[10px] text-surface-600">
          <span>r — rerun</span>
          <span>s — stop</span>
          <span>click step — pin</span>
        </div>
      </div>
    </div>
  )
}
