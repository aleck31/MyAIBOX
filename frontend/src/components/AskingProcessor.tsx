import { useState, useEffect, useCallback, useRef } from 'react'
import { getAskingConfig } from '../api/client'
import { readSSE } from '../api/sse'
import ModelSelector from './ModelSelector'
import type { AskingConfig, AskingHistory } from '../types/asking'

const STORAGE_KEY = 'asking-processor-state'

function loadState() {
  try {
    const s = sessionStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : {}
  } catch { return {} }
}

function saveState(state: Record<string, unknown>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export default function AskingProcessor() {
  const saved = loadState()
  const [config, setConfig] = useState<AskingConfig | null>(null)
  const [input, setInput] = useState(saved.input ?? '')
  const [thinking, setThinking] = useState(saved.thinking ?? '')
  const [response, setResponse] = useState(saved.response ?? '')
  const [history, setHistory] = useState<AskingHistory[]>(saved.history ?? [])
  const [modelId, setModelId] = useState(saved.modelId ?? '')
  const [customPrompt, setCustomPrompt] = useState(saved.customPrompt ?? '')
  const [files, setFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [thinkingOpen, setThinkingOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    saveState({ input, thinking, response, history, modelId, customPrompt })
  }, [input, thinking, response, history, modelId, customPrompt])

  useEffect(() => {
    getAskingConfig().then((cfg) => {
      setConfig(cfg)
      if (!modelId && cfg.models.length) setModelId(cfg.models[0].model_id)
    })
  }, [])

  const handleProcess = useCallback(async () => {
    if (!input.trim() || loading) return
    setLoading(true)
    setThinking('')
    setResponse('')
    setThinkingOpen(true)

    const formData = new FormData()
    formData.append('text', input)
    formData.append('history', JSON.stringify(history))
    formData.append('model_id', modelId)
    formData.append('custom_prompt', customPrompt)
    files.forEach((f) => formData.append('files', f))

    try {
      const res = await fetch('/api/asking/process', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      })

      let thinkBuf = ''
      let respBuf = ''
      await readSSE(res, {
        onText: (delta) => { respBuf += delta; setResponse(respBuf) },
        onReasoning: (delta) => { thinkBuf += delta; setThinking(thinkBuf) },
        onError: (msg) => setResponse(msg),
      })

      // Update history after completion
      if (respBuf) {
        setHistory((h) => [
          ...h,
          { role: 'user', content: input },
          { role: 'assistant', content: respBuf },
        ])
        setFiles([])
      }
    } catch (err) {
      setResponse('An error occurred.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [input, history, modelId, files, loading])

  const handleClear = useCallback(() => {
    setInput('')
    setThinking('')
    setResponse('')
    setHistory([])
    setCustomPrompt('')
    setFiles([])
    sessionStorage.removeItem(STORAGE_KEY)
  }, [])

  const handleCopy = useCallback((text: string) => {
    navigator.clipboard.writeText(text)
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFiles((prev) => [...prev, ...Array.from(e.target.files!)])
    }
  }, [])

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

  const hasHistory = history.length > 0

  return (
    <div className="asking-processor">
      {/* Top bar */}
      <div className="module-options-bar">
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>
          I think, therefore I am.
        </span>
        <div className="text-options">
          <ModelSelector
            models={config.models}
            value={modelId}
            onChange={setModelId}
          />
        </div>
      </div>

      {/* Main content */}
      <div className="asking-main">
        {/* Left: Input */}
        <div className="asking-input-panel">
          <label className="text-panel-label">Your Question</label>
          <textarea
            className="text-area"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask your question..."
            rows={8}
          />
          {/* Attachments */}
          {files.length > 0 && (
            <div className="asking-attachments">
              {files.map((f, i) => (
                <div key={i} className="composer-attachment-chip">
                  <span className="composer-attachment-name">📎 {f.name}</span>
                  <button
                    className="composer-attachment-remove"
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
          {/* File upload */}
          <div className="attach-file-row">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.txt,.md"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            <button
              className="text-btn text-btn--secondary"
              onClick={() => fileInputRef.current?.click()}
              type="button"
            >
              📎 Attach
            </button>
          </div>

          {/* Options (custom prompt only) */}
          <details className="asking-options">
            <summary>Custom prompt</summary>
            <div className="asking-options-content">
              <label className="text-panel-label">
                [leave empty to use default]
              </label>
              <textarea
                className="text-area asking-prompt-input"
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder="Enter custom prompt template..."
                rows={3}
              />
            </div>
          </details>
        </div>

        {/* Right: Output */}
        <div className="asking-output-panel">
          {/* Thinking (collapsible) */}
          <details className="asking-details" open={thinkingOpen} onToggle={(e) => setThinkingOpen(e.currentTarget.open)}>
            <summary className="asking-summary">
              Thinking
              {thinking && (
                <button className="aui-action-bar-button" onClick={(e) => { e.preventDefault(); handleCopy(thinking) }} title="Copy">
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="5" y="5" width="9" height="9" rx="1.5" />
                    <path d="M10 5V3.5A1.5 1.5 0 008.5 2h-5A1.5 1.5 0 002 3.5v5A1.5 1.5 0 003.5 10H5" />
                  </svg>
                </button>
              )}
            </summary>
            <div className="asking-content asking-thinking">{thinking || 'Thinking process will appear here...'}</div>
          </details>

          {/* Response */}
          <details className="asking-details" open>
            <summary className="asking-summary">
              Final Response
              {response && (
                <button className="aui-action-bar-button" onClick={(e) => { e.preventDefault(); handleCopy(response) }} title="Copy">
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="5" y="5" width="9" height="9" rx="1.5" />
                    <path d="M10 5V3.5A1.5 1.5 0 008.5 2h-5A1.5 1.5 0 002 3.5v5A1.5 1.5 0 003.5 10H5" />
                  </svg>
                </button>
              )}
            </summary>
            <div className="asking-content">{response || 'Response will appear here...'}</div>
          </details>
        </div>
      </div>

      {/* Bottom actions */}
      <div className="text-actions">
        <button className="text-btn text-btn--secondary" onClick={handleClear}>
          🗑️ Clear
        </button>
        <button
          className="text-btn text-btn--primary"
          onClick={handleProcess}
          disabled={loading || !input.trim()}
        >
          {loading ? '💭 Thinking...' : hasHistory ? '🙋 Ask further' : '✨ Go'}
        </button>
      </div>
    </div>
  )
}
