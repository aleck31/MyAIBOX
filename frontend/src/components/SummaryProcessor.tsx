import { useState, useEffect, useCallback } from 'react'
import { getSummaryConfig } from '../api/client'
import type { SummaryConfig } from '../types/summary'

const STORAGE_KEY = 'summary-processor-state'

function loadState() {
  try {
    const s = sessionStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : {}
  } catch { return {} }
}

function saveState(state: Record<string, string>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export default function SummaryProcessor() {
  const saved = loadState()
  const [config, setConfig] = useState<SummaryConfig | null>(null)
  const [input, setInput] = useState(saved.input ?? '')
  const [output, setOutput] = useState(saved.output ?? '')
  const [targetLang, setTargetLang] = useState(saved.targetLang ?? 'Original')
  const [modelId, setModelId] = useState(saved.modelId ?? '')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    saveState({ input, output, targetLang, modelId })
  }, [input, output, targetLang, modelId])

  useEffect(() => {
    getSummaryConfig().then((cfg) => {
      setConfig(cfg)
      if (!modelId && cfg.models.length) setModelId(cfg.models[0].model_id)
    })
  }, [])

  const handleProcess = useCallback(async () => {
    if (!input.trim() || loading) return
    setLoading(true)
    setOutput('')

    try {
      const res = await fetch('/api/summary/process', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: input, target_lang: targetLang, model_id: modelId }),
      })

      const reader = res.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let result = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
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
      setOutput('An error occurred while summarizing.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [input, targetLang, modelId, loading])

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
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>
          Summarize text or webpage content
        </span>
        <div className="text-options">
          <select
            className="top-bar-select"
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
          >
            {config.languages.map((lang) => (
              <option key={lang} value={lang}>{lang}</option>
            ))}
          </select>
          <select
            className="top-bar-select"
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            style={{ minWidth: 200 }}
          >
            {config.models.map((m) => (
              <option key={m.model_id} value={m.model_id}>{m.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Text areas */}
      <div className="text-panels">
        <div className="text-panel">
          <div className="text-panel-header">
            <label className="text-panel-label">Text or URL</label>
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
            placeholder="Enter text or paste a URL (@url) to summarize..."
            rows={12}
          />
        </div>
        <div className="text-panel">
          <div className="text-panel-header">
            <label className="text-panel-label">Summary</label>
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
            placeholder="Summary will appear here..."
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
          {loading ? '⏳ Summarizing...' : '▶️ Summarize'}
        </button>
      </div>
    </div>
  )
}
