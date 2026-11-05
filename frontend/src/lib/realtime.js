const RETRY_BASE_MS = 1000
const RETRY_MAX_MS = 30000

export function connectRealtime({ onStatus, onEvent, refreshSession }) {
  let socket
  let retryTimer
  let retryCount = 0
  let stopped = false
  let refreshing = false

  function scheduleReconnect() {
    if (stopped || retryTimer) return
    const delay = Math.min(RETRY_BASE_MS * 2 ** retryCount, RETRY_MAX_MS)
    retryCount += 1
    retryTimer = window.setTimeout(() => {
      retryTimer = null
      connect()
    }, delay)
  }

  function connect() {
    if (stopped) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/events/`)
    onStatus('connecting')

    socket.onopen = () => {
      retryCount = 0
      onStatus('connected')
    }

    socket.onmessage = ({ data }) => {
      try {
        const event = JSON.parse(data)
        if (typeof event.type === 'string') onEvent(event)
      } catch {
        onStatus('error')
      }
    }

    socket.onerror = () => onStatus('disconnected')

    socket.onclose = async ({ code }) => {
      if (stopped) return
      onStatus('disconnected')
      if (code === 4401 && !refreshing) {
        refreshing = true
        const refreshed = await refreshSession()
        refreshing = false
        if (!refreshed || stopped) return
      }
      scheduleReconnect()
    }
  }

  connect()

  return () => {
    stopped = true
    if (retryTimer) window.clearTimeout(retryTimer)
    socket?.close()
  }
}
