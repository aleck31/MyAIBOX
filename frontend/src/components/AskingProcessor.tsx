import { useState, useEffect, useCallback, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { authFetch, getAskingConfig } from '../api/client'
import { readSSE } from '../api/sse'
import { Button } from './Button'
import ModelSelector from './ModelSelector'
import { IconTrash, IconMic, IconPaperclip, IconClose, IconToggleOn, IconToggleOff, IconBrain, IconPanelRight } from './icons'
import { useTranscribe } from '../hooks/useTranscribe'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { useStoredState } from '../hooks/useStoredState'
import { resolveDefaultModel } from '../utils/model'
import type { AskingConfig } from '../types/asking'

const STORAGE_KEY = 'asking-processor-state'

// One round of the research thread: the question, its reasoning, and the answer.
interface QABlock {
  question: string
  thinking: string
  answer: string
  streaming: boolean
}

function loadState() {
  try {
    const s = sessionStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : {}
  } catch { return {} }
}

function saveState(state: Record<string, unknown>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function CopyButton({ text }: { text: string }) {
  return (
    <button className="aui-action-bar-button" onClick={() => navigator.clipboard.writeText(text)} title="Copy">
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="5" y="5" width="9" height="9" rx="1.5" />
        <path d="M10 5V3.5A1.5 1.5 0 008.5 2h-5A1.5 1.5 0 002 3.5v5A1.5 1.5 0 003.5 10H5" />
      </svg>
    </button>
  )
}

export default function AskingProcessor() {
  const saved = loadState()
  const [config, setConfig] = useState<AskingConfig | null>(null)
  const [input, setInput] = useState<string>(saved.input ?? '')
  const [blocks, setBlocks] = useState<QABlock[]>(saved.blocks ?? [])
  // Model is a cross-session preference → localStorage (persists across tabs reopens)
  const [modelId, setModelId] = useStoredState<string>('asking-model', '')
  const [customPrompt, setCustomPrompt] = useState<string>(saved.customPrompt ?? '')
  const [files, setFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [partialTranscript, setPartialTranscript] = useState('')
  const [pendingAutoSend, setPendingAutoSend] = useState(false)
  // UI preferences persist across tabs/reopens (localStorage); the session
  // draft (input/blocks/customPrompt) stays per-tab in sessionStorage below.
  const [autoSend, setAutoSend] = useStoredState<boolean>('asking-autosend', false)
  const [railWidth, setRailWidth] = useStoredState<number>('asking-rail-width', 280)
  const [railOpen, setRailOpen] = useStoredState<boolean>('asking-rail-open', true)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const threadRef = useRef<HTMLDivElement>(null)
  const blockRefs = useRef<Array<HTMLElement | null>>([])

  // On narrow screens the rail floats as an overlay instead of taking a column.
  const isNarrow = useMediaQuery('(max-width: 900px)')

  useEffect(() => {
    saveState({ input, blocks, customPrompt })
  }, [input, blocks, customPrompt])

  useEffect(() => {
    getAskingConfig().then((cfg) => {
      setConfig(cfg)
      // First visit (no stored choice) → module default, not models[0].
      if (!modelId && cfg.models.length) {
        setModelId(resolveDefaultModel(cfg.models, cfg.default_model))
      }
    })
  }, [])

  // Keep the latest answer in view as it streams.
  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight })
  }, [blocks])

  // Click a question in the rail index → scroll its block into view.
  const scrollToBlock = useCallback((i: number) => {
    blockRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  // Drag the rail's left edge to resize it.
  const onRailResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = railWidth
    const onMove = (ev: MouseEvent) => {
      const w = startW + (startX - ev.clientX)
      setRailWidth(Math.min(480, Math.max(200, w)))
    }
    const onUp = () => {
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [railWidth])

  // ── Voice input ──────────────────────────────────────────────────────────
  const partialRef = useRef('')

  const appendToInput = useCallback((text: string) => {
    const seg = text.trim()
    if (!seg) return
    setInput(prev => {
      const t = prev.trimEnd()
      return t ? `${t} ${seg}` : seg
    })
  }, [])

  const transcribe = useTranscribe({
    onPartial: (text) => { partialRef.current = text; setPartialTranscript(text) },
    onFinal: (text) => { partialRef.current = ''; setPartialTranscript(''); appendToInput(text) },
    onError: (msg) => { console.warn('[transcribe]', msg); partialRef.current = ''; setPartialTranscript('') },
  })

  // Finalize-timeout net: commit the last partial if no final landed.
  const wasFinalizingRef = useRef(false)
  useEffect(() => {
    if (wasFinalizingRef.current && !transcribe.isFinalizing && partialRef.current) {
      appendToInput(partialRef.current)
      partialRef.current = ''
      setPartialTranscript('')
    }
    wasFinalizingRef.current = transcribe.isFinalizing
  }, [transcribe.isFinalizing, appendToInput])

  const toggleMic = useCallback(() => {
    if (transcribe.isFinalizing) return
    if (transcribe.isRecording) {
      transcribe.stop()  // keeps WS open; server flushes the final
      if (autoSend) setPendingAutoSend(true)
    } else {
      partialRef.current = ''
      setPartialTranscript('')
      transcribe.start()
    }
  }, [transcribe, autoSend])

  // ── Ask ──────────────────────────────────────────────────────────────────
  const handleProcess = useCallback(async () => {
    const submitText = input.trim()
    if (!submitText || loading) return
    setLoading(true)

    // History = all prior completed rounds, flattened to role/content pairs.
    const history = blocks.flatMap(b => [
      { role: 'user', content: b.question },
      { role: 'assistant', content: b.answer },
    ])

    // Append a fresh block for this question and clear the composer.
    setBlocks(prev => [...prev, { question: submitText, thinking: '', answer: '', streaming: true }])
    setInput('')
    setPartialTranscript('')

    const formData = new FormData()
    formData.append('text', submitText)
    formData.append('history', JSON.stringify(history))
    formData.append('model_id', modelId)
    formData.append('custom_prompt', customPrompt)
    files.forEach((f) => formData.append('files', f))
    setFiles([])

    const patchLast = (patch: Partial<QABlock>) =>
      setBlocks(prev => prev.map((b, i) => i === prev.length - 1 ? { ...b, ...patch } : b))

    try {
      const res = await authFetch('/api/asking/process', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      })
      let thinkBuf = ''
      let respBuf = ''
      await readSSE(res, {
        onText: (delta) => { respBuf += delta; patchLast({ answer: respBuf }) },
        onReasoning: (delta) => { thinkBuf += delta; patchLast({ thinking: thinkBuf }) },
        onError: (msg) => patchLast({ answer: msg }),
      })
    } catch (err) {
      patchLast({ answer: 'An error occurred.' })
      console.error(err)
    } finally {
      patchLast({ streaming: false })
      setLoading(false)
    }
  }, [input, blocks, modelId, customPrompt, files, loading])

  // Auto-send fires once recording AND finalizing both end (final committed).
  useEffect(() => {
    if (pendingAutoSend && !transcribe.isRecording && !transcribe.isFinalizing && input.trim() && !loading) {
      setPendingAutoSend(false)
      handleProcess()
    }
  }, [pendingAutoSend, transcribe.isRecording, transcribe.isFinalizing, input, loading, handleProcess])

  const handleClear = useCallback(() => {
    setInput('')
    setPartialTranscript('')
    setBlocks([])
    setCustomPrompt('')
    setFiles([])
    sessionStorage.removeItem(STORAGE_KEY)
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFiles((prev) => [...prev, ...Array.from(e.target.files!)])
    }
  }, [])

  const onComposerKeyDown = useCallback((e: React.KeyboardEvent) => {
    // Enter sends; Shift+Enter inserts a newline.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleProcess()
    }
  }, [handleProcess])

  if (!config) {
    return (
      <div className="state-screen">
        <div className="state-spinner">
          <div className="spinner-ring" />
          <span className="state-text">Loading</span>
        </div>
      </div>
    )
  }

  const submitText = input.trim()
  const displayValue = (transcribe.isRecording || transcribe.isFinalizing) && partialTranscript
    ? `${input}${input ? ' ' : ''}${partialTranscript}`
    : input
  const micActive = transcribe.isRecording || transcribe.isFinalizing

  const customPromptField = (
    <details className="asking-prompt asking-rail-section">
      <summary className="asking-prompt-summary">
        <svg className="asking-prompt-chevron" width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 2l4 3-4 3" />
        </svg>
        Custom prompt
      </summary>
      <textarea
        className="asking-prompt-textarea"
        value={customPrompt}
        onChange={(e) => setCustomPrompt(e.target.value)}
        placeholder="Optional system prompt to steer answers…"
        rows={6}
      />
    </details>
  )

  return (
    <div className="asking-layout">
      {/* Main column: its own section bar + research thread + composer.
          The rail sits alongside (full height), matching the Chat workspace
          layout for visual consistency. */}
      <div className="asking-main">
        <div className="section-bar">
          <div className="section-actions" style={{ marginLeft: 'auto' }}>
            <ModelSelector models={config.models} value={modelId} onChange={setModelId} />
            <button
              className={`bar-icon-btn${railOpen ? ' active' : ''}`}
              onClick={() => setRailOpen(v => !v)}
              title="Toggle questions panel"
            >
              <IconPanelRight size={14} />
            </button>
          </div>
        </div>

        {/* Stacked Q/A blocks — document style, not chat bubbles */}
        <div className="asking-thread" ref={threadRef}>
            {blocks.length === 0 ? (
              <div className="asking-thread-empty">Ask anything — follow up to go deeper.</div>
            ) : (
              blocks.map((b, i) => (
                <article key={i} className="asking-qa" ref={(el) => { blockRefs.current[i] = el }}>
                  <div className="asking-qa-question">
                    <span className="asking-qa-num">{String(i + 1).padStart(2, '0')}</span>
                    {b.question}
                  </div>

                  {b.thinking && (
                    <details className="asking-qa-thinking">
                      <summary>
                        <IconBrain size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                        Reasoning
                      </summary>
                      <div className="asking-qa-thinking-body">{b.thinking}</div>
                    </details>
                  )}

                  <div className="asking-qa-answer aui-md">
                    {b.answer
                      ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{b.answer}</ReactMarkdown>
                      : <span className="asking-qa-pending">{b.streaming ? 'Thinking…' : ''}</span>}
                    {b.answer && !b.streaming && (
                      <div className="asking-qa-actions"><CopyButton text={b.answer} /></div>
                    )}
                  </div>
                </article>
              ))
            )}
          </div>

          {/* Composer — entry point for every (follow-up) question */}
          <div className="asking-composer">
            {files.length > 0 && (
              <div className="asking-attachments">
                {files.map((f, i) => (
                  <div key={i} className="composer-attachment-chip">
                    <span className="composer-attachment-name">
                      <IconPaperclip size={12} style={{ verticalAlign: '-1px', marginRight: 4 }} />
                      {f.name}
                    </span>
                    <button className="composer-attachment-remove" onClick={() => setFiles(files.filter((_, j) => j !== i))}>
                      <IconClose size={11} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <textarea
              className="asking-composer-input"
              value={displayValue}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onComposerKeyDown}
              placeholder={
                transcribe.isRecording ? 'Listening…'
                  : blocks.length ? 'Ask a follow-up…'
                  : 'Ask your question…'
              }
              rows={3}
              readOnly={micActive}
            />

            <div className="asking-composer-bar">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*,.pdf,.txt,.md"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
              <Button onClick={() => fileInputRef.current?.click()} title="Attach file">
                <IconPaperclip size={14} />
                <span className="composer-btn-label">Attach</span>
              </Button>
              <Button
                style={{ marginLeft: 'auto' }}
                variant={transcribe.isRecording ? 'danger' : undefined}
                title={transcribe.isRecording ? 'Stop' : 'Start voice input'}
                onClick={toggleMic}
                disabled={transcribe.isFinalizing}
              >
                <IconMic size={14} />
                <span className="composer-btn-label">
                  {transcribe.isRecording ? 'Stop' : transcribe.isFinalizing ? '…' : 'Speak'}
                </span>
              </Button>
              <button
                type="button"
                role="switch"
                aria-checked={autoSend}
                className="asking-autosend-toggle"
                onClick={() => setAutoSend(v => !v)}
                title={autoSend ? 'Auto-send after voice input: on' : 'Auto-send after voice input: off'}
              >
                {autoSend ? <IconToggleOn size={18} /> : <IconToggleOff size={18} />}
                Auto-send
              </button>
              {blocks.length > 0 && (
                <Button onClick={handleClear} title="Clear thread">
                  <IconTrash size={14} />
                  <span className="composer-btn-label">Clear</span>
                </Button>
              )}
              <Button
                variant="primary"
                onClick={handleProcess}
                disabled={loading || !submitText || transcribe.isRecording}
              >
                {loading ? '💭 Thinking…' : blocks.length ? 'Ask further' : 'Ask'}
              </Button>
            </div>

            {/* Custom prompt falls inline only when the rail is unavailable. */}
            {(!railOpen || isNarrow) && customPromptField}
          </div>
      </div>

      {/* Narrow + open → dim the main area behind the floating rail. */}
      {railOpen && isNarrow && (
        <div className="asking-rail-backdrop" onClick={() => setRailOpen(false)} />
      )}

      {/* Right rail — header (aligned to section bar) + questions index + custom prompt. */}
      {railOpen && (
        <aside
          className={`asking-rail${isNarrow ? ' asking-rail--overlay' : ''}`}
          style={isNarrow ? undefined : { width: railWidth }}
        >
          {!isNarrow && <div className="asking-rail-resizer" onMouseDown={onRailResize} title="Drag to resize" />}
          <div className="asking-rail-header">
            <span className="asking-rail-title">
              Questions <span className="asking-rail-count">({blocks.length})</span>
            </span>
            <button className="bar-icon-btn" onClick={() => setRailOpen(false)} title="Close">
              <IconClose size={14} />
            </button>
          </div>
          <div className="asking-rail-section asking-rail-questions">
            {blocks.length === 0 ? (
              <div className="asking-rail-empty">Your questions will be indexed here.</div>
            ) : (
              <ol className="asking-rail-index">
                {blocks.map((b, i) => (
                  <li key={i}>
                    <button
                      className="asking-rail-item"
                      onClick={() => { scrollToBlock(i); if (isNarrow) setRailOpen(false) }}
                      title={b.question}
                    >
                      <span className="asking-qa-num">{String(i + 1).padStart(2, '0')}</span>
                      <span className="asking-rail-item-text">{b.question}</span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </div>
          {/* On narrow screens custom prompt lives inline under the composer,
              so the overlay rail only carries the questions index. */}
          {!isNarrow && customPromptField}
        </aside>
      )}
    </div>
  )
}
