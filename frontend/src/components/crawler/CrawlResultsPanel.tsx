import { useState } from 'react'
import {
  Globe,
  MousePointer,
  FormInput,
  FileSearch,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Radar,
  Clock,
  Code2,
  Tag,
} from 'lucide-react'
import { clsx } from 'clsx'
import { formatDistanceToNow } from 'date-fns'
import { crawlApi } from '../../services/api'
import { Button } from '../ui/Button'
import type { CrawlManifest, CrawlPageResult } from '../../types'

interface PageElement {
  tag: string
  role: string | null
  text: string | null
  selector: string
  element_type: string | null
  attributes: Record<string, string>
}

interface PageDetail {
  page_url: string
  page_title: string | null
  elements: PageElement[]
  forms: Array<{
    action: string | null
    method: string
    fields: Array<{
      tag: string
      name: string | null
      type: string | null
      placeholder: string | null
      required: boolean
      label: string | null
    }>
  }>
}

interface CrawlResultsPanelProps {
  suiteId: string
  manifest: CrawlManifest
  onRerun: () => void
}

const ELEMENT_TYPE_COLORS: Record<string, string> = {
  button: 'bg-blue-500/15 text-blue-300 border-blue-500/20',
  link: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/20',
  'input-text': 'bg-violet-500/15 text-violet-300 border-violet-500/20',
  'input-email': 'bg-violet-500/15 text-violet-300 border-violet-500/20',
  'input-password': 'bg-red-500/15 text-red-300 border-red-500/20',
  'input-checkbox': 'bg-amber-500/15 text-amber-300 border-amber-500/20',
  'input-radio': 'bg-amber-500/15 text-amber-300 border-amber-500/20',
  select: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20',
  textarea: 'bg-violet-500/15 text-violet-300 border-violet-500/20',
  input: 'bg-violet-500/15 text-violet-300 border-violet-500/20',
}

function elementTypeColor(type: string | null): string {
  if (!type) return 'bg-surface-700/50 text-surface-400 border-surface-600/40'
  return ELEMENT_TYPE_COLORS[type] ?? 'bg-surface-700/50 text-surface-400 border-surface-600/40'
}

function screenshotUrl(suiteId: string, page: CrawlPageResult): string | null {
  if (!page.screenshot_file) return null
  return `/artifacts/${suiteId}/crawl/${page.screenshot_file}`
}

export function CrawlResultsPanel({ suiteId, manifest, onRerun }: CrawlResultsPanelProps) {
  const [selectedIndex, setSelectedIndex] = useState<number>(0)
  const [pageDetail, setPageDetail] = useState<PageDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [expandedForms, setExpandedForms] = useState<Set<number>>(new Set())
  const [isMinimized, setIsMinimized] = useState(true)

  const selectedPage = manifest.pages[selectedIndex] ?? null

  const handleSelectPage = async (page: CrawlPageResult) => {
    if (page.index === selectedIndex && pageDetail) return
    setSelectedIndex(page.index)
    setPageDetail(null)
    setDetailError(null)
    setExpandedForms(new Set())
    setLoadingDetail(true)
    try {
      const data = await crawlApi.page(suiteId, page.index)
      setPageDetail(data as PageDetail)
    } catch {
      setDetailError('Failed to load page details.')
    } finally {
      setLoadingDetail(false)
    }
  }

  // Auto-load first page on mount via useEffect equivalent (run on first render)
  const [autoLoaded, setAutoLoaded] = useState(false)
  if (!autoLoaded && manifest.pages.length > 0) {
    setAutoLoaded(true)
    // Can't call async directly; schedule for next microtask
    Promise.resolve().then(() => handleSelectPage(manifest.pages[0]))
  }

  const toggleForm = (i: number) =>
    setExpandedForms(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })

  return (
    <div className="rounded-xl border border-surface-800 overflow-hidden bg-surface-950 mb-6">
      {/* ── Header ── */}
      <button
        onClick={() => setIsMinimized(v => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-surface-900 border-b border-surface-800 hover:bg-surface-800/60 transition-colors cursor-pointer text-left"
      >
        <div className="flex items-center gap-3">
          <Radar className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-semibold text-surface-200">Crawl Results</span>
          <div className="flex items-center gap-3 text-xs text-surface-500">
            <span className="flex items-center gap-1">
              <Globe className="w-3 h-3" />
              {manifest.total_pages} pages
            </span>
            <span className="flex items-center gap-1">
              <MousePointer className="w-3 h-3" />
              {manifest.total_elements} elements
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDistanceToNow(new Date(manifest.crawled_at), { addSuffix: true })}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={e => { e.stopPropagation(); onRerun() }} className="h-7 text-xs px-3">
            <Radar className="w-3 h-3" />
            Re-run
          </Button>
          <span className="text-surface-500 p-1 rounded hover:text-surface-200 transition-colors">
            {isMinimized ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </span>
        </div>
      </button>

      {/* ── Split Panel ── */}
      {!isMinimized && <div className="flex" style={{ minHeight: '520px', maxHeight: '640px' }}>
        {/* ─ Left: Page List ─ */}
        <div className="w-[300px] flex-shrink-0 border-r border-surface-800 flex flex-col overflow-y-auto bg-surface-900/50">
          {manifest.pages.map(page => {
            const isSelected = page.index === selectedIndex
            const displayUrl = page.url.replace(/^https?:\/\//, '').replace(/\/$/, '')

            return (
              <button
                key={page.index}
                onClick={() => handleSelectPage(page)}
                className={clsx(
                  'w-full text-left flex items-start gap-3 px-3 py-2.5 border-b border-surface-800/60 transition-colors cursor-pointer',
                  isSelected
                    ? 'bg-primary-500/10 border-l-2 border-l-primary-500/60'
                    : 'hover:bg-surface-800/40 border-l-2 border-l-transparent',
                )}
              >
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-medium text-surface-200 truncate leading-tight">
                    {displayUrl || '/'}
                  </p>
                  {page.page_title && (
                    <p className="text-[10px] text-surface-500 truncate mt-0.5">{page.page_title}</p>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] text-surface-500 flex items-center gap-0.5">
                      <MousePointer className="w-2.5 h-2.5" />
                      {page.element_count}
                    </span>
                    {page.form_count > 0 && (
                      <span className="text-[10px] text-surface-500 flex items-center gap-0.5">
                        <FormInput className="w-2.5 h-2.5" />
                        {page.form_count}
                      </span>
                    )}
                  </div>
                </div>

                <span className="text-[10px] font-mono text-surface-600 flex-shrink-0 pt-0.5">
                  {page.index + 1}
                </span>
              </button>
            )
          })}
        </div>

        {/* ─ Right: Screenshot + Elements ─ */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {selectedPage ? (
            <>
              {/* Screenshot */}
              <div className="h-52 flex-shrink-0 bg-surface-950 border-b border-surface-800 relative overflow-hidden">
                {screenshotUrl(suiteId, selectedPage) ? (
                  <img
                    src={screenshotUrl(suiteId, selectedPage)!}
                    alt={selectedPage.page_title ?? selectedPage.url}
                    className="w-full h-full object-cover object-top"
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-surface-600">
                    <FileSearch className="w-8 h-8 opacity-30" />
                    <p className="text-xs">No screenshot captured</p>
                  </div>
                )}
                {/* URL overlay */}
                <div className="absolute bottom-0 left-0 right-0 px-3 py-1.5 bg-gradient-to-t from-black/80 to-transparent">
                  <p className="text-[11px] text-surface-300 truncate">{selectedPage.url}</p>
                </div>
              </div>

              {/* Elements / Forms */}
              <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
                {loadingDetail && (
                  <div className="flex items-center justify-center h-20 text-surface-500 text-xs gap-2">
                    <div className="w-3 h-3 border border-surface-600 border-t-primary-500 rounded-full animate-spin" />
                    Loading elements…
                  </div>
                )}

                {detailError && (
                  <p className="text-xs text-red-400 text-center py-4">{detailError}</p>
                )}

                {pageDetail && !loadingDetail && (
                  <>
                    {/* Element count header */}
                    <div className="flex items-center gap-2 text-xs text-surface-500 mb-1">
                      <MousePointer className="w-3 h-3" />
                      <span className="font-semibold text-surface-300">{pageDetail.elements.length}</span> interactive elements
                      {pageDetail.forms.length > 0 && (
                        <span className="ml-2 flex items-center gap-1">
                          <FormInput className="w-3 h-3" />
                          <span className="font-semibold text-surface-300">{pageDetail.forms.length}</span> forms
                        </span>
                      )}
                    </div>

                    {/* Elements list */}
                    {pageDetail.elements.length === 0 ? (
                      <p className="text-xs text-surface-600 text-center py-4">No interactive elements found</p>
                    ) : (
                      <div className="space-y-1">
                        {pageDetail.elements.map((el, i) => (
                          <div
                            key={i}
                            className="flex items-start gap-2 px-2 py-1.5 rounded-md bg-surface-900 border border-surface-800/60 hover:border-surface-700/60 transition-colors"
                          >
                            {/* Type badge */}
                            <span className={clsx(
                              'text-[10px] px-1.5 py-0.5 rounded border font-mono flex-shrink-0 mt-0.5',
                              elementTypeColor(el.element_type),
                            )}>
                              {el.element_type ?? el.tag}
                            </span>

                            <div className="flex-1 min-w-0 space-y-0.5">
                              {/* Selector */}
                              <div className="flex items-center gap-1 min-w-0">
                                <Code2 className="w-2.5 h-2.5 text-surface-500 flex-shrink-0" />
                                <code className="text-[10px] text-emerald-400/80 font-mono truncate">
                                  {el.selector}
                                </code>
                              </div>

                              {/* Text content */}
                              {el.text && (
                                <div className="flex items-center gap-1 min-w-0">
                                  <Tag className="w-2.5 h-2.5 text-surface-500 flex-shrink-0" />
                                  <span className="text-[10px] text-surface-400 truncate">
                                    {el.text.substring(0, 80)}
                                  </span>
                                </div>
                              )}

                              {/* Key attributes inline */}
                              {Object.keys(el.attributes).length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-0.5">
                                  {Object.entries(el.attributes).slice(0, 3).map(([k, v]) => (
                                    <span key={k} className="text-[9px] bg-surface-800 text-surface-500 px-1 rounded">
                                      {k}={String(v).substring(0, 30)}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Forms section */}
                    {pageDetail.forms.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs font-semibold text-surface-400 mb-2 flex items-center gap-1.5">
                          <FormInput className="w-3 h-3" /> Forms
                        </p>
                        {pageDetail.forms.map((form, fi) => (
                          <div key={fi} className="rounded-md border border-surface-800 bg-surface-900 mb-2 overflow-hidden">
                            <button
                              onClick={() => toggleForm(fi)}
                              className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-surface-800/50 transition-colors cursor-pointer"
                            >
                              <span className="text-[11px] text-surface-300">
                                Form {fi + 1}
                                {form.action && (
                                  <span className="ml-2 text-surface-500 font-normal">→ {form.action}</span>
                                )}
                                <span className="ml-2 text-surface-600 font-normal uppercase text-[9px]">{form.method}</span>
                              </span>
                              <span className="flex items-center gap-1 text-[10px] text-surface-500">
                                {form.fields.length} fields
                                {expandedForms.has(fi)
                                  ? <ChevronDown className="w-3 h-3" />
                                  : <ChevronRight className="w-3 h-3" />}
                              </span>
                            </button>
                            {expandedForms.has(fi) && (
                              <div className="px-3 pb-2 space-y-1 border-t border-surface-800">
                                {form.fields.map((field, ffi) => (
                                  <div key={ffi} className="flex items-center gap-2 py-1">
                                    <span className={clsx(
                                      'text-[9px] px-1 py-0.5 rounded border font-mono flex-shrink-0',
                                      elementTypeColor(field.type ? `input-${field.type}` : 'input'),
                                    )}>
                                      {field.type ?? field.tag}
                                    </span>
                                    <span className="text-[10px] text-surface-400 truncate">
                                      {field.label ?? field.name ?? field.placeholder ?? `field-${ffi}`}
                                    </span>
                                    {field.required && (
                                      <span className="text-[9px] text-red-400 ml-auto flex-shrink-0">required</span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-surface-600 gap-2">
              <FileSearch className="w-8 h-8 opacity-30" />
              <p className="text-xs">Select a page to view details</p>
            </div>
          )}
        </div>
      </div>}
    </div>
  )
}
