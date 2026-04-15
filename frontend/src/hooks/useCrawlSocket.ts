import { useRef, useCallback, useState } from 'react'
import type { WsCrawlMessage, WsCrawlPage, WsCrawlComplete, WsCrawlError } from '../types'

export type CrawlSocketStatus = 'idle' | 'crawling' | 'completed' | 'error'

export function useCrawlSocket(suiteId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const [pages, setPages] = useState<WsCrawlPage[]>([])
  const [status, setStatus] = useState<CrawlSocketStatus>('idle')
  const [latestScreenshot, setLatestScreenshot] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [summary, setSummary] = useState<WsCrawlComplete | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const connect = useCallback(() => {
    if (!suiteId) return
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/crawl/${suiteId}`)

    ws.onopen = () => {
      setConnected(true)
      setStatus('crawling')
    }
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)

    ws.onmessage = (e) => {
      const msg: WsCrawlMessage = JSON.parse(e.data)
      switch (msg.event) {
        case 'crawl_page': {
          const pageMsg = msg as WsCrawlPage
          setPages(prev => [...prev, pageMsg])
          if (pageMsg.screenshot_base64) {
            setLatestScreenshot(pageMsg.screenshot_base64)
          }
          break
        }
        case 'crawl_complete':
          setSummary(msg as WsCrawlComplete)
          setStatus('completed')
          break
        case 'crawl_error': {
          const errMsg = msg as WsCrawlError
          setErrorMsg(errMsg.error)
          setStatus('error')
          break
        }
      }
    }

    wsRef.current = ws
  }, [suiteId])

  const disconnect = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
    setConnected(false)
  }, [])

  const reset = useCallback(() => {
    setPages([])
    setStatus('idle')
    setLatestScreenshot(null)
    setSummary(null)
    setErrorMsg(null)
  }, [])

  return { pages, status, connected, latestScreenshot, summary, errorMsg, connect, reset, disconnect }
}
