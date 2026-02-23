import { useState, useEffect, useCallback } from 'react'
import { getTextConfig } from '../api/client'
import type { TextConfig } from '../types/text'

const STORAGE_KEY = 'text-processor-state'

function loadState() {
  try {
    const s = sessionStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : {}
  } catch { return {} }
}

function saveState(state: Record<string, string>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export default function TextProcessor() {
  const saved = loadState()
  const [config, setConfig] = useState<TextConfig | null>(null)
  const [input, setInput] = useState(saved.input ?? '')
  const [output, setOutput] = useState(saved.output ?? '')
  const [operation, setOperation] = useState(saved.operation ?? 'proofread')
  const [targetLang, setTargetLang] = useState(saved.targetLang ?? 'en_US')
  const [style, setStyle] = useState(saved.style ?? '正常')
  const [loading, setLoading] = useState(false)

  // Persist state on change
  useEffect(() => {
    saveState({ input, output, operation, targetLang, style })
  }, [input, output, operation, targetLang, style])

  useEffect(() => {
    getTextConfig().then(setConfig)
  }, [])

  const handleProcess = useCallback(async () => {
    if (!input.trim() || loading) return
    setLoading(true)
    setOutput('')

    try {
      const res = await fetch('/api/text/process', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: input, operation, target_lang: targetLang, style }),
      })

      const reader = res.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let result = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        // Parse SSE lines for TEXT_MESSAGE_CONTENT events
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            if (evt.type === 'TEXT_MESSAGE_CONTENT') {
              result += evt.delta
              setOutput(result)
            } else if (evt.type === 'RUN_ERROR') {
              setOutput(evt.message || 'An error occurred.')
            }
          } catch { /* skip non-JSON lines */ }
        }
      }
    } catch (err) {
      setOutput('An error occurred while processing your text.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [input, operation, targetLang, style, loading])

  const handleClear = useCallback(() => {
    setInput('')
    setOutput('')
    sessionStorage.removeItem(STORAGE_KEY)
  }, [])

  const handleCopy = useCallback((text: string) => {
    navigator.clipboard.writeText(text)
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

  return (
    <div className="text-processor">
      {/* Controls bar */}
      <div className="module-options-bar">
        <div className="text-operations">
          {config.operations.map((op) => (
            <button
              key={op.key}
              className={`text-op-btn${operation === op.key ? ' active' : ''}`}
              onClick={() => setOperation(op.key)}
            >
              {op.label}
            </button>
          ))}
        </div>
        <div className="text-options">
          {operation === 'rewrite' && (
            <select
              className="top-bar-select"
              value={style}
              onChange={(e) => setStyle(e.target.value)}
            >
              {config.styles.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          )}
          <select
            className="top-bar-select"
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
          >
            {config.languages.map((lang) => (
              <option key={lang} value={lang}>{lang}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Text areas */}
      <div className="text-panels">
        <div className="text-panel">
          <div className="text-panel-header">
            <label className="text-panel-label">Original Text</label>
            {input && (
              <button className="aui-action-bar-button" onClick={() => handleCopy(input)} title="Copy">
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="5" y="5" width="9" height="9" rx="1.5" />
                  <path d="M10 5V3.5A1.5 1.5 0 008.5 2h-5A1.5 1.5 0 002 3.5v5A1.5 1.5 0 003.5 10H5" />
                </svg>
              </button>
            )}
          </div>
          <textarea
            className="text-area"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter your text here..."
            rows={12}
          />
        </div>
        <div className="text-panel">
          <div className="text-panel-header">
            <label className="text-panel-label">Processed Result</label>
            {output && (
              <button className="aui-action-bar-button" onClick={() => handleCopy(output)} title="Copy">
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="5" y="5" width="9" height="9" rx="1.5" />
                  <path d="M10 5V3.5A1.5 1.5 0 008.5 2h-5A1.5 1.5 0 002 3.5v5A1.5 1.5 0 003.5 10H5" />
                </svg>
              </button>
            )}
          </div>
          <textarea
            className="text-area"
            value={output}
            readOnly
            placeholder="Result will appear here..."
            rows={12}
          />
        </div>
      </div>

      {/* Action buttons */}
      <div className="text-actions">
        <button className="text-btn text-btn--secondary" onClick={handleClear}>
          🗑️ Clear
        </button>
        <button
          className="text-btn text-btn--primary"
          onClick={handleProcess}
          disabled={loading || !input.trim()}
        >
          {loading ? '⏳ Processing...' : '▶️ Process'}
        </button>
      </div>
    </div>
  )
}
