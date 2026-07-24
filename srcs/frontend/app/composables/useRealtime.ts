export type RealtimeStatus = 'disconnected' | 'connecting' | 'connected'

export type RealtimeMessage<T = Record<string, unknown>> = {
  type: string
  payload: T
}

type RealtimeHandler = (message: RealtimeMessage) => void

const HEARTBEAT_INTERVAL_MS = 25_000
const CONNECTION_TIMEOUT_MS = 60_000
const MAX_RECONNECT_DELAY_MS = 30_000

const status = shallowRef<RealtimeStatus>('disconnected')
const listeners = new Map<string, Set<RealtimeHandler>>()
let socket: WebSocket | null = null
let shouldRun = false
let currentToken: string | null = null
let serviceUrl = ''
let reconnectAttempt = 0
let reconnectTimer: ReturnType<typeof setTimeout> | undefined
let heartbeatTimer: ReturnType<typeof setInterval> | undefined
let lastMessageAt = 0

/** Owns the application's single, persistent browser WebSocket. */
export function useRealtime() {
  function start(token: string, baseUrl = '') {
    if (!import.meta.client) return
    const unchanged = shouldRun && currentToken === token && serviceUrl === baseUrl
    if (unchanged && socket && socket.readyState <= WebSocket.OPEN) return

    stop()
    shouldRun = true
    currentToken = token
    serviceUrl = baseUrl
    connect()
  }

  function stop() {
    shouldRun = false
    currentToken = null
    reconnectAttempt = 0
    clearTimers()
    const activeSocket = socket
    socket = null
    if (activeSocket && activeSocket.readyState < WebSocket.CLOSING) {
      activeSocket.close(1000, 'Client stopped')
    }
    status.value = 'disconnected'
  }

  function send(type: string, payload: Record<string, unknown> = {}) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return false
    socket.send(JSON.stringify({ type, payload }))
    return true
  }

  function onMessage<T = Record<string, unknown>>(
    type: string,
    handler: (message: RealtimeMessage<T>) => void
  ) {
    const handlers = listeners.get(type) || new Set<RealtimeHandler>()
    const registered = handler as RealtimeHandler
    handlers.add(registered)
    listeners.set(type, handlers)

    const unsubscribe = () => {
      handlers.delete(registered)
      if (!handlers.size) listeners.delete(type)
    }
    onScopeDispose(unsubscribe)
    return unsubscribe
  }

  return {
    status: readonly(status),
    start,
    stop,
    send,
    onMessage
  }
}

function connect() {
  if (!shouldRun || !currentToken || !import.meta.client) return

  status.value = 'connecting'
  const url = websocketUrl(serviceUrl, currentToken)
  const nextSocket = new WebSocket(url)
  socket = nextSocket

  nextSocket.addEventListener('open', () => {
    if (socket !== nextSocket) return
    status.value = 'connected'
    reconnectAttempt = 0
    lastMessageAt = Date.now()
    startHeartbeat()
  })

  nextSocket.addEventListener('message', (event) => {
    if (socket !== nextSocket) return
    lastMessageAt = Date.now()
    dispatch(event.data)
  })

  nextSocket.addEventListener('close', () => {
    if (socket !== nextSocket) return
    socket = null
    status.value = 'disconnected'
    if (heartbeatTimer) clearInterval(heartbeatTimer)
    heartbeatTimer = undefined
    scheduleReconnect()
  })

  nextSocket.addEventListener('error', () => {
    nextSocket.close()
  })
}

function dispatch(raw: unknown) {
  if (typeof raw !== 'string') return

  try {
    const message = JSON.parse(raw) as Partial<RealtimeMessage>
    if (typeof message.type !== 'string' || !message.payload) return
    for (const handler of [...(listeners.get(message.type) || [])]) {
      try {
        handler(message as RealtimeMessage)
      } catch (cause) {
        console.error(`Realtime handler failed for ${message.type}`, cause)
      }
    }
  } catch {
    // Ignore malformed server messages and keep the long-lived connection healthy.
  }
}

function startHeartbeat() {
  if (heartbeatTimer) clearInterval(heartbeatTimer)
  heartbeatTimer = setInterval(() => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return
    if (Date.now() - lastMessageAt > CONNECTION_TIMEOUT_MS) {
      socket.close(4000, 'Connection timed out')
      return
    }
    socket.send(JSON.stringify({
      type: 'connection.ping',
      payload: { clientTime: new Date().toISOString() }
    }))
  }, HEARTBEAT_INTERVAL_MS)
}

function scheduleReconnect() {
  if (!shouldRun || reconnectTimer) return
  const exponentialDelay = Math.min(
    1000 * 2 ** reconnectAttempt,
    MAX_RECONNECT_DELAY_MS
  )
  const delay = exponentialDelay + Math.round(Math.random() * 500)
  reconnectAttempt += 1
  reconnectTimer = setTimeout(() => {
    reconnectTimer = undefined
    connect()
  }, delay)
}

function clearTimers() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  if (heartbeatTimer) clearInterval(heartbeatTimer)
  reconnectTimer = undefined
  heartbeatTimer = undefined
}

function websocketUrl(baseUrl: string, token: string) {
  const url = new URL(baseUrl || window.location.origin, window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `${url.pathname.replace(/\/+$/, '')}/api/ws`
  url.search = ''
  url.searchParams.set('accessToken', token)
  return url.toString()
}
