import { useState, useEffect, useCallback } from 'react'
import { authFetch, getSummaryConfig } from '../api/client'
import { readSSE } from '../api/sse'
import { Button } from './Button'
import ModelSelector from './ModelSelector'
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
      const res = await authFetch('/api/summary/process', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: input, target_lang: targetLang, model_id: modelId }),
      })

      let result = ''
      await readSSE(res, {
        onText: (delta) => { result += delta; setOutput(result) },
        onError: (msg) => setOutput(msg),
      })
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
    <div className="module-layout">
      {/* Controls bar */}
      <div className="module-options-bar">
        <div className="module-options">
          <select
            className="select"
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
          >
            {config.languages.map((lang) => (
              <option key={lang} value={lang}>{lang}</option>
            ))}
          </select>
          <ModelSelector models={config.models} value={modelId} onChange={setModelId} />
        </div>
      </div>

      {/* Text areas */}
      <div className="module-panel-main module-panel-main--equal">
        <div className="module-panel-left">
          <div className="panel-header">
            <label className="panel-label">Text or URL</label>
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
            className="panel-textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter text or paste a URL (@url) to summarize..."
          />
        </div>
        <div className="module-panel-right">
          <div className="panel-header">
            <label className="panel-label">Summary</label>
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
            className="panel-textarea"
            value={output}
            readOnly
            placeholder="Summary will appear here..."
          />
        </div>
      </div>

      {/* Action buttons */}
      <div className="module-action-bar">
        <Button onClick={handleClear}>🗑️ Clear</Button>
        <Button
          variant="primary"
          onClick={handleProcess}
          disabled={loading || !input.trim()}
        >
          {loading ? '⏳ Summarizing...' : '▶️ Summarize'}
        </Button>
      </div>
    </div>
  )
}
