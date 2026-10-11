import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import type { HttpAgent } from '@ag-ui/client'
import { ResumableAgent } from '../api/resumableAgent'
import { RESUME_ATTEMPTS, resumeDelayMs, sleep, watchForStall, whenVisible } from '../api/sse'
import type { RunErrorEvent, ReasoningMessageContentEvent, TextMessageContentEvent, ToolCallStartEvent, ToolCallArgsEvent, ToolCallEndEvent, ToolCallResultEvent, CustomEvent } from '@ag-ui/core'
import { useExternalStoreRuntime } from '@assistant-ui/react'
import type { ThreadMessageLike, AppendMessage } from '@assistant-ui/react'
import { FileUploadAdapter } from './FileUploadAdapter'
import { MODEL_UNAVAILABLE } from '../utils/model'

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

/** AG-UI 1.x allows structured tool-result content; the UI keeps a JSON/text string. */
function toolResultText(content: ToolCallResultEvent['content']): string {
  return typeof content === 'string' ? content : JSON.stringify(content)
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
  // Emit tool-call parts so assistant-ui renders registered ToolUIs.
  // Dedupe by id — duplicate toolCallId crashes assistant-ui (Duplicate key).
  const seenToolIds = new Set<string>()
  for (const tc of msg.toolCalls ?? []) {
    if (seenToolIds.has(tc.id)) continue
    seenToolIds.add(tc.id)
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
  /** AG-UI CUSTOM events out-of-band (e.g. workspace_updated). */
  onCustomEvent?: (name: string, value: unknown) => void
  /** Extra JSON merged into the runAgent payload (server reads `forwarded_props`). */
  forwardedProps?: Record<string, unknown>
  /** Called when the message history is edited locally (e.g. edit/retry). Caller typically persists to backend. */
  onMessagesEdited?: (messages: Array<{ role: 'user' | 'assistant'; content: string }>) => void
  /** Called when the server reports the selected model is gone, so the caller can reload its model list. */
  onModelUnavailable?: () => void
}

// Module-level cache: survives route changes, cleared on tab close
const _msgCache = new Map<string, LocalMessage[]>()
const _agentCache = new Map<string, ResumableAgent>()

/** One reply in flight, as the client sees it. */
interface ActiveRun {
  id: string
  assistantId: string
  /** Agent messages as they were when the run started: what a replay starts from. */
  baseMessages: HttpAgent['messages']
  /** The server said how it ended (RUN_FINISHED / RUN_ERROR), or we gave up. */
  finished: boolean
  /** The user pressed Stop, or sent a newer message. */
  stopped: boolean
  /** A re-attach loop is running. */
  resuming: boolean
  /** We aborted a stalled connection ourselves, in order to re-attach. */
  recycle: boolean
  subscriber?: Parameters<HttpAgent['runAgent']>[1]
  /** Stops the stalled-connection watcher. */
  unwatch?: () => void
}

// The reply in flight, per thread, so a page reload can re-attach to it
const _runKey = (threadId: string) => `chat-run:${threadId}`
function loadActiveRun(threadId: string): { id: string; assistantId: string } | null {
  try { const raw = sessionStorage.getItem(_runKey(threadId)); return raw ? JSON.parse(raw) : null } catch { return null }
}
function saveActiveRun(threadId: string, run: { id: string; assistantId: string } | null) {
  try {
    if (run) sessionStorage.setItem(_runKey(threadId), JSON.stringify({ id: run.id, assistantId: run.assistantId }))
    else sessionStorage.removeItem(_runKey(threadId))
  } catch { /* quota */ }
}

/** A failed fetch (offline, connection reset, page frozen) is a TypeError; HTTP and protocol errors are not. */
function isConnectionLoss(error: Error): boolean {
  return error instanceof TypeError
}

// Per-thread sessionStorage mirror so conversation survives a refresh
// ("no clear = it stays"). _msgCache is the fast route-switch cache; sessionStorage
// is the refresh-proof backstop. cloud_sync (DDB) is independent and only adds cross-device sync.
const _msgsKey = (threadId: string) => `chat-msgs:${threadId}`
function loadStoredMsgs(threadId: string): LocalMessage[] | null {
  try {
    const raw = sessionStorage.getItem(_msgsKey(threadId))
    return raw ? (JSON.parse(raw) as LocalMessage[]) : null
  } catch { return null }
}
function saveStoredMsgs(threadId: string, msgs: LocalMessage[]) {
  try { sessionStorage.setItem(_msgsKey(threadId), JSON.stringify(msgs)) } catch { /* quota */ }
}

/** Clear cached state for a thread (e.g. on conversation clear) */
export function clearRuntimeCache(threadId: string) {
  _msgCache.delete(threadId)
  _agentCache.delete(threadId)
  try { sessionStorage.removeItem(_msgsKey(threadId)); sessionStorage.removeItem(_runKey(threadId)) } catch { /* ignore */ }
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

/** True for the error the fetch layer raises when the user stops a run or leaves the page. */
function isAbort(message: string, name?: string): boolean {
  return name === 'AbortError' || /\babort(ed)?\b/i.test(message)
}

export function useAGUIRuntime({ url, threadId, initialMessages = [], onCustomEvent, forwardedProps, onMessagesEdited, onModelUnavailable }: UseAGUIRuntimeOptions) {
  // Ref so subscriber captures the latest callback without re-binding.
  const onCustomEventRef = useRef(onCustomEvent)
  onCustomEventRef.current = onCustomEvent
  // Ref so the runAgent call always sees the current props without re-creating the agent.
  const forwardedPropsRef = useRef(forwardedProps)
  forwardedPropsRef.current = forwardedProps
  const onMessagesEditedRef = useRef(onMessagesEdited)
  onMessagesEditedRef.current = onMessagesEdited
  const onModelUnavailableRef = useRef(onModelUnavailable)
  onModelUnavailableRef.current = onModelUnavailable
  const [localMessages, setLocalMessagesRaw] = useState<LocalMessage[]>(() => {
    // Restore priority: _msgCache (route switch) → sessionStorage (refresh)
    // → initialMessages (from backend DDB, e.g. fresh open / cross-device).
    const cached = _msgCache.get(threadId)
    if (cached) return cached
    const stored = loadStoredMsgs(threadId)
    if (stored) { _msgCache.set(threadId, stored); return stored }

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

  // Wrap setLocalMessages to mirror into _msgCache (route switch) + sessionStorage (refresh).
  const setLocalMessages: typeof setLocalMessagesRaw = useCallback((update) => {
    setLocalMessagesRaw(prev => {
      const next = typeof update === 'function' ? update(prev) : update
      _msgCache.set(threadId, next)
      saveStoredMsgs(threadId, next)
      return next
    })
  }, [threadId])

  const agentRef = useRef<ResumableAgent>(
    _agentCache.get(threadId) ??
    new ResumableAgent({
      url,
      threadId,
      // After a reload the screen is restored from sessionStorage; the agent starts from the same messages
      // (minus a reply still in flight, which a re-attach replays) so what is sent matches what is shown.
      initialMessages: localMessages.length
        ? localMessages
            .filter(m => !m.isStreaming && (m.role === 'user' || m.role === 'assistant'))
            .map(m => ({ id: m.id, role: m.role, content: m.content }))
        : initialMessages.map((m, i) => ({ id: `hist-${i}`, role: m.role, content: extractText(m.content) })),
    })
  )

  // Cache agent on first create
  if (!_agentCache.has(threadId)) {
    _agentCache.set(threadId, agentRef.current)
  }

  const localMessagesRef = useRef(localMessages)
  localMessagesRef.current = localMessages

  const activeRunRef = useRef<ActiveRun | null>(null)

  /** The run is over for this client: stop watching it and forget it for reloads. */
  const endRun = useCallback((run: ActiveRun) => {
    run.unwatch?.()
    run.unwatch = undefined
    if (activeRunRef.current === run) saveActiveRun(threadId, null)
  }, [threadId])

  const stopStreaming = useCallback((assistantId: string) => {
    setLocalMessages(prev => prev.map(m => (m.id === assistantId ? { ...m, isStreaming: false } : m)))
  }, [setLocalMessages])

  const showError = useCallback((assistantId: string, message: string, keepText = false) => {
    setLocalMessages(prev =>
      prev.map(m => {
        if (m.id !== assistantId) return m
        const content = keepText && m.content ? `${m.content}\n\nError: ${message}` : `Error: ${message}`
        return { ...m, content, isStreaming: false }
      })
    )
  }, [setLocalMessages])

  /**
   * Re-attach to a reply whose connection was lost. The server keeps producing it (backend/api/runs.py), so the
   * reply is replayed from the start: what was drawn is cleared first and the agent's messages go back to
   * what they were when the run started.
   */
  const startResume = useCallback((run: ActiveRun) => {
    if (run.resuming) return
    run.resuming = true
    run.recycle = false
    void (async () => {
      const agent = agentRef.current
      for (let attempt = 0; attempt < RESUME_ATTEMPTS && !run.finished && !run.stopped; attempt++) {
        await sleep(resumeDelayMs(attempt))
        await whenVisible()
        if (run.finished || run.stopped) break
        agent.setMessages(run.baseMessages)
        setLocalMessages(prev =>
          prev.map(m => (m.id === run.assistantId
            ? { ...m, content: '', reasoning: undefined, toolCalls: undefined, isStreaming: true }
            : m))
        )
        try {
          await agent.connectAgent({ runId: run.id, forwardedProps: forwardedPropsRef.current }, run.subscriber)
        } catch (err) {
          const e = err as Error
          const retry = isConnectionLoss(e) || (run.recycle && isAbort(e.message, e.name))
          run.recycle = false
          // Anything else: the reply is gone from the server (restarted, or kept too long).
          if (!retry) break
        }
      }
      run.resuming = false
      endRun(run)
      if (!run.finished && !run.stopped) {
        run.finished = true
        showError(run.assistantId, 'the connection was lost and the reply could not be recovered. Send your message again.')
      } else {
        stopStreaming(run.assistantId)   // finished while re-attached: onRunFinalized stays quiet in that case
      }
    })()
  }, [setLocalMessages, showError, stopStreaming, endRun])

  /** A run as this client follows it; `id` is the server's run id (new for a new message, kept on a reload). */
  const makeRun = useCallback((assistantId: string, id: string): ActiveRun => {
    const agent = agentRef.current
    // A newer message replaces a reply that is still being produced or recovered (the server does the same).
    const previous = activeRunRef.current
    if (previous) { previous.stopped = true; previous.unwatch?.() }
    const run: ActiveRun = {
      id,
      assistantId,
      baseMessages: [...agent.messages],
      finished: false,
      stopped: false,
      resuming: false,
      recycle: false,
    }
    activeRunRef.current = run
    saveActiveRun(threadId, run)
    // A connection that went silent (a phone froze the page) is dropped and re-attached; one that keeps
    // receiving, such as a desktop tab in the background, is left alone.
    run.unwatch = watchForStall(() => agent.lastDataAt, () => {
      if (run.finished || run.stopped) return
      if (run.resuming && agent.isRunning === false) return   // between re-attach tries: nothing to drop
      run.recycle = true
      agent.abortRun()
    })

    run.subscriber = {
          onTextMessageContentEvent({ event }: { event: TextMessageContentEvent }) {
            setLocalMessages(prev =>
              prev.map(m =>
                m.id === run.assistantId ? { ...m, content: m.content + event.delta } : m
              )
            )
          },
          onReasoningMessageContentEvent({ event }: { event: ReasoningMessageContentEvent }) {
            setLocalMessages(prev =>
              prev.map(m =>
                m.id === run.assistantId
                  ? { ...m, reasoning: (m.reasoning ?? '') + event.delta }
                  : m
              )
            )
          },
          onToolCallStartEvent({ event }: { event: ToolCallStartEvent }) {
            setLocalMessages(prev =>
              prev.map(m => {
                if (m.id !== run.assistantId) return m
                // GPT-5 Responses API re-emits start for the same toolCallId; dedupe.
                if ((m.toolCalls ?? []).some(tc => tc.id === event.toolCallId)) return m
                return { ...m, toolCalls: [...(m.toolCalls ?? []), { id: event.toolCallId, name: event.toolCallName, args: '' }] }
              })
            )
          },
          onToolCallArgsEvent({ event }: { event: ToolCallArgsEvent }) {
            setLocalMessages(prev =>
              prev.map(m =>
                m.id === run.assistantId
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
                if (m.id !== run.assistantId) return m
                const toolCalls = (m.toolCalls ?? []).map(tc =>
                  tc.id === event.toolCallId ? { ...tc, result: toolResultText(event.content) } : tc
                )
                return { ...m, toolCalls }
              })
            )
          },
          onRunFinishedEvent() {
            run.finished = true
          },
          onRunFinalized() {
            if (run.resuming) return
            // The stream ended without the server saying how the reply ended: the connection was cut, or we
            // dropped a stalled one (an aborted run ends here without onRunFailed). Collect the reply.
            if (!run.finished && !run.stopped) { startResume(run); return }
            endRun(run)
            stopStreaming(run.assistantId)
          },
          // The client reports a server-sent RUN_ERROR only here (onRunFailed is for transport failures),
          // so show it here too; otherwise the reply stays an empty bubble.
          onRunErrorEvent({ event }: { event: RunErrorEvent }) {
            // Stop (or leaving the page) surfaces here as "signal is aborted": not a failure, keep what streamed.
            if (isAbort(event.message)) { stopStreaming(run.assistantId); return }
            run.finished = true
            endRun(run)
            showError(run.assistantId, event.message, true)
            if (event.code === MODEL_UNAVAILABLE) onModelUnavailableRef.current?.()
          },
          onRunFailed({ error }: { error: Error }) {
            if (run.resuming) return                      // the re-attach loop handles its own failures
            if (!run.finished && !run.stopped) {
              // Our own abort of a stalled connection, or the connection dying (a phone sent to the
              // background): the server still has the reply.
              if ((run.recycle && isAbort(error.message, error.name)) || isConnectionLoss(error)) { startResume(run); return }
            }
            run.finished = true
            endRun(run)
            if (isAbort(error.message, error.name)) stopStreaming(run.assistantId)
            else showError(run.assistantId, error.message)
          },
          onCustomEvent({ event }: { event: CustomEvent }) {
            onCustomEventRef.current?.(event.name, event.value)
          },
        }

    return run
  }, [setLocalMessages, startResume, stopStreaming, showError, endRun, threadId])

  const runAgent = useCallback((assistantId: string) => {
    const run = makeRun(assistantId, generateId())
    agentRef.current.runAgent({ runId: run.id, forwardedProps: forwardedPropsRef.current }, run.subscriber).catch(() => {})
  }, [makeRun])

  // A reload while a reply was being produced: the server kept producing it, so re-attach and replay it.
  useEffect(() => {
    const saved = loadActiveRun(threadId)
    if (!saved) return
    const reply = localMessagesRef.current.find(m => m.id === saved.assistantId)
    if (!reply?.isStreaming) { saveActiveRun(threadId, null); return }
    startResume(makeRun(saved.assistantId, saved.id))
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
    const run = activeRunRef.current
    if (run && !run.finished) {
      run.stopped = true
      endRun(run)
      // The server keeps a reply going when its connection closes, so Stop has to say so explicitly.
      const query = new URLSearchParams({ agent_id: String(forwardedPropsRef.current?.agent_id ?? ''), run_id: run.id })
      fetch(`${url}/cancel?${query}`, { method: 'POST', credentials: 'include' }).catch(() => {})
    }
    agentRef.current.abortRun()
    setLocalMessages(prev => prev.map(m => (m.isStreaming ? { ...m, isStreaming: false } : m)))
  }, [url, endRun])

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

    // Notify caller so backend can persist the trimmed history (e.g. on edit/retry).
    onMessagesEditedRef.current?.(trimmed.map(m => ({ role: m.role, content: m.content })))

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
