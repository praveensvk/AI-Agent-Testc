import { useRef, useEffect, useCallback, useState } from 'react'
import type { WsMessage, WsTestStep } from '../types'
import { runApi } from '../services/api'

const TERMINAL = new Set(['passed', 'failed', 'error'])

export function useTestRunSocket(runId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const [steps, setSteps] = useState<WsTestStep[]>([])
  const [status, setStatus] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [currentUrl, setCurrentUrl] = useState<string | null>(null)

  // Synchronous ref mirrors status so callbacks always see the latest value
  // without depending on React's async render cycle.
  const statusRef = useRef<string | null>(null)
  const setStatusSynced = useCallback((s: string) => {
    statusRef.current = s
    setStatus(s)
  }, [])

  // Resolve final status from DB with up to 3 retries.
  const resolveFinalStatus = useCallback((id: string) => {
    let attempts = 0
    const tryFetch = () => {
      attempts++
      runApi.get(id)
        .then(run => {
          if (TERMINAL.has(run.status)) {
            setStatusSynced(run.status)
          } else if (attempts < 3) {
            // Run might still be committing – retry after a short delay
            setTimeout(tryFetch, 1500)
          }
        })
        .catch(() => { if (attempts < 3) setTimeout(tryFetch, 1500) })
    }
    tryFetch()
  }, [setStatusSynced])

  const connect = useCallback(() => {
    if (!runId) return
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/test-runs/${runId}`)

    ws.onopen = () => setConnected(true)

    ws.onclose = () => {
      setConnected(false)
      // If we never received a terminal status_change, resolve it from the DB.
      // statusRef.current is updated synchronously so it's reliable here.
      if (!TERMINAL.has(statusRef.current ?? '')) {
        resolveFinalStatus(runId)
      }
    }

    ws.onerror = () => setConnected(false)

    ws.onmessage = (e) => {
      const msg: WsMessage = JSON.parse(e.data)
      switch (msg.event) {
        case 'status_change':
          setStatusSynced(msg.status)
          if (TERMINAL.has(msg.status)) {
            ws.close()
          }
          break
        case 'test_step':
          setSteps(prev => [...prev, msg])
          if (msg.action === 'navigate' && msg.value) {
            setCurrentUrl(msg.value)
          }
          break
        case 'artifact_ready':
          break
      }
    }

    wsRef.current = ws
  }, [runId, resolveFinalStatus, setStatusSynced])

  const disconnect = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  const reset = useCallback(() => {
    setSteps([])
    statusRef.current = null
    setStatus(null)
    setCurrentUrl(null)
  }, [])

  useEffect(() => {
    connect()
    return disconnect
  }, [connect, disconnect])

  return { steps, status, connected, currentUrl, reset, disconnect }
}
