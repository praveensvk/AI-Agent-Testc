import { useState, useRef, useEffect } from 'react'
import {
  Globe,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  Wifi,
  WifiOff,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  FileSearch,
  MousePointer,
  FormInput,
  X,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { WsCrawlPage, WsCrawlComplete } from '../../types'
import type { CrawlSocketStatus } from '../../hooks/useCrawlSocket'

interface CrawlRunnerProps {
  suiteId: string
  suiteName: string
  baseUrl: string
  pages: WsCrawlPage[]
  status: CrawlSocketStatus
  connected: boolean
  latestScreenshot: string | null
  summary: WsCrawlComplete | null
  errorMsg: string | null
  onStop?: () => void
  onDismiss?: () => void
}

export function CrawlRunner({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  suiteId: _suiteId,
  suiteName,
  baseUrl,
  pages,
  status,
  connected,
  latestScreenshot,
  summary,
  errorMsg,
  onStop,
  onDismiss,
}: CrawlRunnerProps) {
  const [pinnedIndex, setPinnedIndex] = useState<number | null>(null)
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const [isListExpanded, setIsListExpanded] = useState(true)
  const [isMinimized, setIsMinimized] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)

  const isCrawling = status === 'crawling'
  const isDone = status === 'completed'
  const isError = status === 'error'
  const isComplete = isDone || isError

  // Get screenshot to show in preview
  const activeIndex = pinnedIndex ?? hoveredIndex
  const previewPage = activeIndex !== null ? pages[activeIndex] : pages[pages.length - 1]
  const previewScreenshot = previewPage?.screenshot_base64 ?? latestScreenshot
  const previewUrl = previewPage?.url ?? baseUrl

  const totalElements = pages.reduce((sum, p) => sum + p.element_count, 0)
  const totalForms = pages.reduce((sum, p) => sum + p.form_count, 0)

  // Track start time for duration
  const startTimeRef = useRef<number>(Date.now())
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!isCrawling) return
    startTimeRef.current = Date.now()
    const id = setInterval(() => setElapsed(Date.now() - startTimeRef.current), 500)
    return () => clearInterval(id)
  }, [isCrawling])

  // Auto-scroll log
  useEffect(() => {
    if (isCrawling && logRef.current && pinnedIndex === null) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [pages.length, isCrawling, pinnedIndex])

  return (
    <div className="flex flex-col rounded-xl border border-surface-800 overflow-hidden bg-surface-950">
      {/* ═══ Top Toolbar ═══ */}
      <div className="flex items-center justify-between h-10 px-3 bg-surface-900 border-b border-surface-800 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className={clsx(
            'w-2 h-2 rounded-full',
            isCrawling && 'bg-blue-400 animate-pulse',
            isDone && 'bg-emerald-400',
            isError && 'bg-red-400',
            status === 'idle' && 'bg-surface-600',
          )} />
          <span className="text-xs font-medium text-surface-300">
            {isCrawling ? 'Crawling site…' : isDone ? 'Crawl complete' : isError ? 'Crawl failed' : 'Auto-Gen'}
          </span>
          <span className="text-xs text-surface-600">— {suiteName}</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Stats */}
          {pages.length > 0 && (
            <div className="flex items-center gap-3 text-xs mr-2">
              <span className="flex items-center gap-1 text-primary-400">
                <Globe className="w-3 h-3" />
                {pages.length} page{pages.length !== 1 ? 's' : ''}
              </span>
              <span className="flex items-center gap-1 text-surface-400">
                <MousePointer className="w-3 h-3" />
                {totalElements} elements
              </span>
              {totalForms > 0 && (
                <span className="flex items-center gap-1 text-surface-400">
                  <FormInput className="w-3 h-3" />
                  {totalForms} forms
                </span>
              )}
              {(isCrawling || isComplete) && (
                <span className="flex items-center gap-1 text-surface-500">
                  <Clock className="w-3 h-3" />
                  {isDone || isError
                    ? `${((summary ? Date.now() - startTimeRef.current : elapsed) / 1000).toFixed(1)}s`
                    : `${(elapsed / 1000).toFixed(1)}s`}
                </span>
              )}
            </div>
          )}

          {/* Connection */}
          <div className={clsx('p-1 rounded', connected ? 'text-emerald-400' : 'text-surface-600')}>
            {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          </div>

          {/* Minimize / Expand */}
          <button
            onClick={() => setIsMinimized(v => !v)}
            className="p-1 rounded text-surface-400 hover:text-surface-200 hover:bg-surface-800 transition-colors cursor-pointer"
            title={isMinimized ? 'Expand' : 'Minimize'}
          >
            {isMinimized ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>

          {/* Stop */}
          {isCrawling && onStop && (
            <button
              onClick={onStop}
              className="p-1 rounded text-surface-400 hover:text-red-400 hover:bg-surface-800 transition-colors cursor-pointer"
              title="Stop crawl"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Dismiss */}
          {isComplete && onDismiss && (
            <button
              onClick={onDismiss}
              className="p-1 rounded text-surface-400 hover:text-surface-200 hover:bg-surface-800 transition-colors cursor-pointer"
              title="Dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ═══ Main Split Panel ═══ */}
      {!isMinimized && <div className="flex" style={{ height: '420px' }}>
        {/* ─── Left: Page Log ─── */}
        <div className="w-[400px] flex-shrink-0 flex flex-col border-r border-surface-800 bg-surface-900">
          {/* Collapsible header */}
          <button
            onClick={() => setIsListExpanded(v => !v)}
            className={clsx(
              'flex items-center gap-2 px-3 py-2 text-left w-full border-b border-surface-800',
              'hover:bg-surface-800/50 transition-colors cursor-pointer',
              isDone && 'bg-emerald-500/5',
              isError && 'bg-red-500/5',
            )}
          >
            {isDone ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            ) : isError ? (
              <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            ) : (
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />
            )}
            {isListExpanded
              ? <ChevronDown className="w-3 h-3 text-surface-500 flex-shrink-0" />
              : <ChevronRight className="w-3 h-3 text-surface-500 flex-shrink-0" />
            }
            <span className="text-xs font-semibold text-surface-200 flex-1">
              Pages discovered
            </span>
            <span className="text-[10px] text-surface-500">{pages.length}</span>
          </button>

          {/* Page list */}
          <div
            ref={logRef}
            className={clsx('flex-1 overflow-y-auto', !isListExpanded && 'hidden')}
          >
            {pages.length === 0 && isCrawling && (
              <div className="flex flex-col items-center justify-center h-full gap-2 text-surface-500">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-xs">Connecting to site…</span>
              </div>
            )}

            {pages.map((page, i) => {
              const isActive = (pinnedIndex ?? hoveredIndex) === i
              const isPinned = pinnedIndex === i
              // Truncate long URLs
              const displayUrl = page.url.replace(/^https?:\/\//, '').replace(/\/$/, '')

              return (
                <div
                  key={i}
                  onMouseEnter={() => !pinnedIndex && setHoveredIndex(i)}
                  onMouseLeave={() => !pinnedIndex && setHoveredIndex(null)}
                  onClick={() => setPinnedIndex(prev => prev === i ? null : i)}
                  className={clsx(
                    'group flex items-start gap-2 px-3 py-2 transition-all cursor-pointer',
                    'border-l-2',
                    isActive ? 'border-l-primary-500/60 bg-primary-500/5' : 'border-l-transparent',
                    !isActive && 'hover:bg-surface-800/40',
                    isPinned && 'ring-1 ring-inset ring-primary-500/20',
                  )}
                >
                  {/* Status icon */}
                  <div className="flex-shrink-0 mt-0.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  </div>

                  {/* Page info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <Globe className="w-3 h-3 text-cyan-400 flex-shrink-0" />
                      <span className="text-[11px] font-medium text-surface-200 truncate">
                        {displayUrl}
                      </span>
                    </div>
                    {page.page_title && (
                      <p className="text-[10px] text-surface-500 truncate mt-0.5 ml-4">
                        {page.page_title}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-1 ml-4">
                      <span className="text-[10px] text-surface-500 flex items-center gap-1">
                        <MousePointer className="w-2.5 h-2.5" />
                        {page.element_count}
                      </span>
                      {page.form_count > 0 && (
                        <span className="text-[10px] text-surface-500 flex items-center gap-1">
                          <FormInput className="w-2.5 h-2.5" />
                          {page.form_count}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Progress indicator */}
                  <span className="text-[10px] font-mono text-surface-600 flex-shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                </div>
              )
            })}

            {/* Currently crawling indicator */}
            {isCrawling && pages.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-2 border-l-2 border-l-blue-500/40">
                <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin flex-shrink-0" />
                <span className="text-[11px] text-blue-400/80">Crawling next page…</span>
              </div>
            )}

            {/* Completion / error bar */}
            {isDone && summary && (
              <div className="mx-3 my-2 p-2 bg-emerald-500/10 border border-emerald-800/30 rounded text-xs text-emerald-400 text-center">
                ✓ Crawled {summary.total_pages} pages · {summary.total_elements} elements discovered
              </div>
            )}
            {isError && errorMsg && (
              <div className="mx-3 my-2 p-2 bg-red-500/10 border border-red-800/30 rounded text-xs text-red-400">
                <p className="font-semibold mb-0.5">Crawl failed</p>
                <p className="text-red-300/70">{errorMsg || 'An unexpected error occurred. Check backend logs for details.'}</p>
              </div>
            )}
          </div>
        </div>

        {/* ─── Right: Screenshot Preview ─── */}
        <div className="flex-1 flex flex-col bg-surface-950 min-w-0">
          {/* URL bar */}
          <div className="flex items-center gap-2 px-3 py-2 bg-surface-900 border-b border-surface-800">
            <div className="flex-1 flex items-center gap-2 px-2.5 py-1 bg-surface-800 rounded text-xs text-surface-400 overflow-hidden">
              <Globe className="w-3 h-3 flex-shrink-0 text-surface-500" />
              <span className="truncate">{previewUrl}</span>
            </div>
            {isCrawling && previewPage && (
              <div className="flex items-center gap-1 text-[10px] text-blue-400">
                <Loader2 className="w-3 h-3 animate-spin" />
              </div>
            )}
          </div>

          {/* Screenshot area */}
          <div className="flex-1 relative overflow-hidden">
            {previewScreenshot ? (
              <img
                src={previewScreenshot}
                alt="Page screenshot"
                className="w-full h-full object-top object-cover"
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-surface-600">
                <FileSearch className="w-10 h-10 opacity-30" />
                <p className="text-xs">
                  {isCrawling ? 'Screenshot will appear after first page crawl' : 'No screenshot available'}
                </p>
              </div>
            )}

            {/* Live crawling overlay on screenshot */}
            {isCrawling && previewScreenshot && (
              <div className="absolute top-2 right-2 flex items-center gap-1.5 px-2 py-1 bg-black/60 rounded-full text-[10px] text-blue-300">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                live
              </div>
            )}

            {/* Pin indicator */}
            {pinnedIndex !== null && (
              <div className="absolute bottom-2 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-black/60 rounded-full text-[10px] text-surface-300">
                Pinned — click page to unpin
              </div>
            )}
          </div>
        </div>
      </div>}
    </div>
  )
}
