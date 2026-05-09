export interface SSECallbacks {
  onText?: (delta: string) => void
  onReasoning?: (delta: string) => void
  onError?: (message: string) => void
  onMetadata?: (data: Record<string, unknown>) => void
  /** AG-UI `CUSTOM` events — used for out-of-band notifications like `workspace_updated`. */
  onCustom?: (name: string, value: unknown) => void
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
        else if (evt.type === 'RUN_ERROR') callbacks.onError?.(evt.message || 'An error occurred.')
        else if (evt.type === 'CUSTOM') callbacks.onCustom?.(evt.name, evt.value)
      } catch { /* incomplete JSON, skip */ }
      eventType = ''
    }
  }
}
