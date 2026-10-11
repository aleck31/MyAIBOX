export interface SSECallbacks {
  onText?: (delta: string) => void
  onReasoning?: (delta: string) => void
  /** `code` is set for errors the client can act on, e.g. `model_unavailable`. */
  onError?: (message: string, code?: string) => void
  onMetadata?: (data: Record<string, unknown>) => void
  /** AG-UI `CUSTOM` events — used for out-of-band notifications like `workspace_updated`. */
  onCustom?: (name: string, value: unknown) => void
  /** RUN_FINISHED or RUN_ERROR arrived: the server says the reply is over. */
  onFinished?: () => void
}

export async function readSSE(res: Response, callbacks: SSECallbacks) {
  const reader = res.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''
  let eventType = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim()
        continue
      }
      if (!line.startsWith('data: ')) continue
      try {
        const evt = JSON.parse(line.slice(6))
        if (eventType === 'metadata') {
          callbacks.onMetadata?.(evt)
        } else if (evt.type === 'TEXT_MESSAGE_CONTENT') callbacks.onText?.(evt.delta)
        else if (evt.type === 'REASONING_MESSAGE_CONTENT') callbacks.onReasoning?.(evt.delta)
        else if (evt.type === 'RUN_ERROR') { callbacks.onError?.(evt.message || 'An error occurred.', evt.code); callbacks.onFinished?.() }
        else if (evt.type === 'RUN_FINISHED') callbacks.onFinished?.()
        else if (evt.type === 'CUSTOM') callbacks.onCustom?.(evt.name, evt.value)
      } catch { /* incomplete JSON, skip */ }
      eventType = ''
    }
  }
}

/** How a reply that lost its connection is re-attached: tries, with a growing pause before each (1s, 2s, 4s, 8s...). */
export const RESUME_ATTEMPTS = 8
export const resumeDelayMs = (attempt: number) => Math.min(1000 * 2 ** attempt, 8000)
/** Coming back to the page after less than this, the connection is assumed fine. */
export const HIDDEN_LONG_ENOUGH_MS = 2000

export const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

/** Resolves once the page is visible (at once if it already is). A hidden page has no working network. */
export function whenVisible(): Promise<void> {
  if (!document.hidden) return Promise.resolve()
  return new Promise(resolve => {
    const onChange = () => {
      if (document.hidden) return
      document.removeEventListener('visibilitychange', onChange)
      resolve()
    }
    document.addEventListener('visibilitychange', onChange)
  })
}

export class ReplyLostError extends Error {}

/**
 * Read a reply the server keeps producing when the connection drops (backend/api/runs.py), re-attaching to it
 * as needed: a phone sent to the background, a screen turned off, a network change.
 *
 * `start` sends the request; `resume` fetches the same reply again, replayed from the start, so `onRestart`
 * must clear whatever was drawn from the earlier attempt. Throws ReplyLostError if the reply cannot be
 * recovered; other errors are passed through.
 */
export async function readResumableSSE(
  start: (signal: AbortSignal) => Promise<Response>,
  resume: (signal: AbortSignal) => Promise<Response>,
  callbacks: SSECallbacks,
  onRestart: () => void,
): Promise<void> {
  let finished = false
  const tracked: SSECallbacks = { ...callbacks, onFinished: () => { finished = true; callbacks.onFinished?.() } }

  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController()
    let recycled = false
    let hiddenAt = 0
    // Back from a while in the background: the connection is probably dead even if nothing has failed yet.
    const onVisibility = () => {
      if (document.hidden) { hiddenAt = Date.now(); return }
      if (hiddenAt && Date.now() - hiddenAt >= HIDDEN_LONG_ENOUGH_MS) { recycled = true; controller.abort() }
    }
    document.addEventListener('visibilitychange', onVisibility)
    try {
      if (attempt > 0) {
        await sleep(resumeDelayMs(attempt - 1))
        await whenVisible()
        onRestart()
      }
      const res = await (attempt === 0 ? start : resume)(controller.signal)
      if (attempt > 0 && res.status === 404) throw new ReplyLostError('The reply is no longer on the server.')
      await readSSE(res, tracked)
      if (finished) return
      // The stream ended without the server saying the reply was over: the connection was cut.
    } catch (err) {
      const lost = err instanceof TypeError || (recycled && (err as Error).name === 'AbortError')
      if (!lost) throw err
    } finally {
      document.removeEventListener('visibilitychange', onVisibility)
    }
    if (attempt + 1 >= RESUME_ATTEMPTS) throw new ReplyLostError('The connection was lost and the reply could not be recovered.')
  }
}
