import { useState, useRef, useCallback, useMemo } from 'react'
import { HttpAgent } from '@ag-ui/client'
import type { ReasoningMessageContentEvent, TextMessageContentEvent, ToolCallStartEvent, ToolCallArgsEvent, ToolCallEndEvent, ToolCallResultEvent } from '@ag-ui/core'
import { useExternalStoreRuntime } from '@assistant-ui/react'
import type { ThreadMessageLike, AppendMessage } from '@assistant-ui/react'
import { FileUploadAdapter } from './FileUploadAdapter'
import { syncHistory } from '../api/client'

function generateId() {
  return crypto.randomUUID()
}

interface LocalAttachment {
  id: string
  name: string
  type: string
  mimeType: string
  dataUrl?: string  // for image preview
}

interface LocalMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  isStreaming?: boolean
  attachments?: LocalAttachment[]
  toolCalls?: LocalToolCall[]
}

interface LocalToolCall {
  id: string
  name: string
  args: string       // JSON string, parsed by assistant-ui
  result?: string    // JSON string of tool result
}

// Implement the following if client-side tool execution is needed in the future:
//   - image content parts → { type: 'image', image: url | data-uri }
function convertLocalMessage(msg: LocalMessage): ThreadMessageLike {
  if (msg.role === 'user') {
    const content: any[] = []
    for (const a of msg.attachments ?? []) {
      if (a.dataUrl && a.mimeType?.startsWith('image/')) {
        content.push({ type: 'image' as const, image: a.dataUrl })
      } else if (a.dataUrl) {
        content.push({ type: 'file' as const, data: a.dataUrl, mimeType: a.mimeType || 'application/octet-stream', filename: a.name })
      }
    }
    if (msg.content) content.push({ type: 'text' as const, text: msg.content })
    return { role: 'user', id: msg.id, content }
  }

  const parts: any[] = []
  if (msg.reasoning) {
    parts.push({ type: 'reasoning' as const, text: msg.reasoning })
  }
  // Emit tool-call parts so assistant-ui renders registered ToolUIs
  for (const tc of msg.toolCalls ?? []) {
    let args: Record<string, unknown> = {}
    try { args = JSON.parse(tc.args) } catch { /* ignore */ }
    let result: unknown = undefined
    try { if (tc.result) result = JSON.parse(tc.result) } catch { result = tc.result }
    parts.push({ type: 'tool-call' as const, toolCallId: tc.id, toolName: tc.name, args, result })
  }
  parts.push({ type: 'text' as const, text: msg.content })

  return {
    role: 'assistant',
    id: msg.id,
    content: parts,
    status: msg.isStreaming ? { type: 'running' } : { type: 'complete', reason: 'stop' },
  }
}

interface UseAGUIRuntimeOptions {
  url: string
  threadId: string
  initialMessages?: Array<{ role: 'user' | 'assistant'; content: unknown }>
}

// Module-level cache: survives route changes, cleared on tab close
const _msgCache = new Map<string, LocalMessage[]>()
const _agentCache = new Map<string, HttpAgent>()

/** Clear cached state for a thread (e.g. on conversation clear) */
export function clearRuntimeCache(threadId: string) {
  _msgCache.delete(threadId)
  _agentCache.delete(threadId)
}

/** Extract text only from content (for HttpAgent which only needs text) */
function extractText(content: unknown): string {
  return parseHistoryContent(content).text
}

/** Convert a server file path to a serveable URL */
function filePathToUrl(p: string): string {
  const name = p.split('/').pop() || ''
  return `/api/upload/file/${name}`
}

/** Check if a filename looks like an image */
function isImageFile(name: string): boolean {
  return /\.(jpg|jpeg|png|gif|webp)$/i.test(name)
}

/** Parse history message content into text + attachments */
function parseHistoryContent(content: unknown): { text: string; attachments: LocalAttachment[] } {
  if (typeof content === 'string') return { text: content, attachments: [] }

  // Array of file paths from load_session_history (file messages)
  if (Array.isArray(content) && content.length > 0 && typeof content[0] === 'string') {
    const attachments: LocalAttachment[] = content.map((p: string, i: number) => ({
      id: `att-${i}`,
      name: p.split('/').pop() || 'file',
      type: 'file',
      mimeType: isImageFile(p) ? 'image/png' : 'application/octet-stream',
      dataUrl: filePathToUrl(p),
    }))
    return { text: '', attachments }
  }

  // AG-UI content array [{type:"text",...},{type:"binary",...}]
  if (Array.isArray(content)) {
    const text = content.filter((p: any) => p.type === 'text').map((p: any) => p.text).join('\n')
    const attachments: LocalAttachment[] = content
      .filter((p: any) => p.type === 'binary' && p.data)
      .map((p: any, i: number) => ({
        id: `att-${i}`,
        name: p.filename || p.data.split('/').pop() || 'file',
        type: 'file',
        mimeType: p.mimeType || 'application/octet-stream',
        dataUrl: isImageFile(p.filename || p.data) ? filePathToUrl(p.data) : undefined,
      }))
    return { text, attachments }
  }

  if (typeof content === 'object' && content && 'text' in content) return { text: (content as any).text, attachments: [] }
  return { text: String(content), attachments: [] }
}

export function useAGUIRuntime({ url, threadId, initialMessages = [] }: UseAGUIRuntimeOptions) {
  const [localMessages, setLocalMessagesRaw] = useState<LocalMessage[]>(() => {
    // Restore from cache if available (route switch)
    const cached = _msgCache.get(threadId)
    if (cached) return cached

    return initialMessages.map((m, i) => {
      const { text, attachments } = parseHistoryContent(m.content)
      return {
        id: `hist-${i}`,
        role: m.role,
        content: text,
        attachments: attachments.length ? attachments : undefined,
      }
    })
  })

  // Wrap setLocalMessages to sync cache
  const setLocalMessages: typeof setLocalMessagesRaw = useCallback((update) => {
    setLocalMessagesRaw(prev => {
      const next = typeof update === 'function' ? update(prev) : update
      _msgCache.set(threadId, next)
      return next
    })
  }, [threadId])

  const agentRef = useRef(
    _agentCache.get(threadId) ??
    new HttpAgent({
      url,
      threadId,
      initialMessages: initialMessages.map((m, i) => ({
        id: `hist-${i}`,
        role: m.role,
        content: extractText(m.content),
      })),
    })
  )

  // Cache agent on first create
  if (!_agentCache.has(threadId)) {
    _agentCache.set(threadId, agentRef.current)
  }

  const localMessagesRef = useRef(localMessages)
  localMessagesRef.current = localMessages

  const runAgent = useCallback((assistantId: string) => {
    agentRef.current
      .runAgent(
        { runId: generateId() },
        {
          onTextMessageContentEvent({ event }: { event: TextMessageContentEvent }) {
            setLocalMessages(prev =>
              prev.map(m =>
                m.id === assistantId ? { ...m, content: m.content + event.delta } : m
              )
            )
          },
          onReasoningMessageContentEvent({ event }: { event: ReasoningMessageContentEvent }) {
            setLocalMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, reasoning: (m.reasoning ?? '') + event.delta }
                  : m
              )
            )
          },
          onToolCallStartEvent({ event }: { event: ToolCallStartEvent }) {
            setLocalMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, toolCalls: [...(m.toolCalls ?? []), { id: event.toolCallId, name: event.toolCallName, args: '' }] }
                  : m
              )
            )
          },
          onToolCallArgsEvent({ event }: { event: ToolCallArgsEvent }) {
            setLocalMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, toolCalls: (m.toolCalls ?? []).map(tc => tc.id === event.toolCallId ? { ...tc, args: tc.args + event.delta } : tc) }
                  : m
              )
            )
          },
          onToolCallEndEvent(_params: { event: ToolCallEndEvent }) {
            // Tool call args finalized; result arrives via onToolCallResultEvent
          },
          onToolCallResultEvent({ event }: { event: ToolCallResultEvent }) {
            setLocalMessages(prev =>
              prev.map(m => {
                if (m.id !== assistantId) return m
                const toolCalls = (m.toolCalls ?? []).map(tc =>
                  tc.id === event.toolCallId ? { ...tc, result: event.content } : tc
                )
                return { ...m, toolCalls }
              })
            )
          },
          onRunFinalized() {
            setLocalMessages(prev =>
              prev.map(m => (m.id === assistantId ? { ...m, isStreaming: false } : m))
            )
          },
          onRunFailed({ error }: { error: Error }) {
            setLocalMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: `Error: ${error.message}`, isStreaming: false }
                  : m
              )
            )
          },
        }
      )
      .catch(() => {})
  }, [])

  const fileUploadAdapter = useMemo(() => new FileUploadAdapter(), [])

  const onNew = useCallback(
    async (msg: AppendMessage) => {
      const text = msg.content
        .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
        .map(p => p.text)
        .join('')

      // Build AG-UI content: text + binary parts from attachments
      const contentParts: Array<Record<string, string>> = []
      if (text) contentParts.push({ type: 'text', text })
      for (const att of msg.attachments ?? []) {
        // Find the server-path content part (not the preview data URL)
        const serverPart = (att.content ?? []).find(
          (c: any) => c.type === 'file' && c.data && !c.data.startsWith('data:')
        ) as Record<string, string> | undefined
        if (serverPart) {
          contentParts.push({
            type: 'binary',
            mimeType: serverPart.mimeType || 'application/octet-stream',
            data: serverPart.data || '',
            filename: att.name || '',
          })
        }
      }

      const userMsgId = generateId()
      const assistantId = generateId()

      agentRef.current.addMessage({
        id: userMsgId,
        role: 'user',
        content: contentParts.length === 1 && contentParts[0].type === 'text'
          ? text
          : contentParts as any,
      })

      // Build local attachments — extract preview data URL from content
      const localAttachments: LocalAttachment[] = []
      for (const att of msg.attachments ?? []) {
        const contents = att.content ?? [] as any[]
        // Find image or file content with data URL
        const imgPart = contents.find((c: any) => c.type === 'image') as any
        const filePart = contents.find((c: any) => c.type === 'file' && c.data?.startsWith('data:')) as any
        localAttachments.push({
          id: att.id,
          name: att.name,
          type: att.type,
          mimeType: (att as any).contentType || '',
          dataUrl: imgPart?.image || filePart?.data,
        })
      }

      setLocalMessages(prev => [
        ...prev,
        { id: userMsgId, role: 'user', content: text, attachments: localAttachments.length ? localAttachments : undefined },
        { id: assistantId, role: 'assistant', content: '', isStreaming: true },
      ])

      runAgent(assistantId)
    },
    [runAgent]
  )

  const onCancel = useCallback(async () => {
    agentRef.current.abortRun()
    setLocalMessages(prev => prev.map(m => (m.isStreaming ? { ...m, isStreaming: false } : m)))
  }, [])

  const onReload = useCallback(async () => {
    const newAssistantId = generateId()
    const prev = localMessagesRef.current
    const lastAssistantIdx = prev.map(m => m.role).lastIndexOf('assistant')
    if (lastAssistantIdx === -1) return

    const withoutLast = prev.slice(0, lastAssistantIdx)
    agentRef.current.setMessages(
      withoutLast.map(m => ({ id: m.id, role: m.role, content: m.content }))
    )
    setLocalMessages([
      ...withoutLast,
      { id: newAssistantId, role: 'assistant', content: '', isStreaming: true },
    ])
    runAgent(newAssistantId)
  }, [runAgent])

  const retractLast = useCallback((): string => {
    const msgs = localMessagesRef.current
    const lastAssistantIdx = msgs.map(m => m.role).lastIndexOf('assistant')
    if (lastAssistantIdx === -1) return ''

    const lastUserIdx = msgs.slice(0, lastAssistantIdx).map(m => m.role).lastIndexOf('user')
    if (lastUserIdx === -1) return ''

    const userText = msgs[lastUserIdx].content
    const trimmed = msgs.slice(0, lastUserIdx)

    agentRef.current.setMessages(
      trimmed.map(m => ({ id: m.id, role: m.role, content: m.content }))
    )
    setLocalMessages(trimmed)

    // Sync to backend session
    syncHistory(trimmed.map(m => ({ role: m.role, content: m.content }))).catch(() => {})

    return userText
  }, [])

  const adapter = useMemo(
    () => ({
      messages: localMessages,
      convertMessage: convertLocalMessage,
      onNew,
      onCancel,
      onReload,
      adapters: {
        attachments: fileUploadAdapter,
      },
    }),
    [localMessages, onNew, onCancel, onReload, fileUploadAdapter]
  )

  const runtime = useExternalStoreRuntime(adapter)

  const getMessages = useCallback(
    () =>
      agentRef.current.messages
        .filter(m => m.role === 'user' || m.role === 'assistant')
        .map(m => ({ role: m.role, content: m.content })),
    []
  )

  return { runtime, getMessages, retractLast }
}
