export interface SSECallbacks {
  onText?: (delta: string) => void
  onReasoning?: (delta: string) => void
  onError?: (message: string) => void
}

export async function readSSE(res: Response, callbacks: SSECallbacks) {
  const reader = res.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const evt = JSON.parse(line.slice(6))
        if (evt.type === 'TEXT_MESSAGE_CONTENT') callbacks.onText?.(evt.delta)
        else if (evt.type === 'REASONING_MESSAGE_CONTENT') callbacks.onReasoning?.(evt.delta)
        else if (evt.type === 'RUN_ERROR') callbacks.onError?.(evt.message || 'An error occurred.')
      } catch { /* incomplete JSON, skip */ }
    }
  }
}
