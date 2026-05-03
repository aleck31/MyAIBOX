import { useState, useEffect, useCallback } from 'react'
import { authFetch, getTextConfig } from '../api/client'
import { readSSE } from '../api/sse'
import { Button } from './Button'
import ModelSelector from './ModelSelector'
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
  const [modelId, setModelId] = useState(saved.modelId ?? '')
  const [loading, setLoading] = useState(false)

  // Persist state on change
  useEffect(() => {
    saveState({ input, output, operation, targetLang, style, modelId })
  }, [input, output, operation, targetLang, style])

  useEffect(() => {
    getTextConfig().then((cfg) => {
      setConfig(cfg)
      if (!modelId && cfg.models?.length) setModelId(cfg.models[0].model_id)
    })
  }, [])

  const handleProcess = useCallback(async () => {
    if (!input.trim() || loading) return
    setLoading(true)
    setOutput('')

    try {
      const res = await authFetch('/api/text/process', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: input, operation, target_lang: targetLang, style, model_id: modelId }),
      })

      let result = ''
      await readSSE(res, {
        onText: (delta) => { result += delta; setOutput(result) },
        onError: (msg) => setOutput(msg),
      })
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
    <div className="module-layout">
      {/* Controls bar */}
      <div className="section-bar">
        <div className="text-operations">
          {config.operations.map((op) => (
            <Button
              key={op.key}
              shape="pill"
              active={operation === op.key}
              onClick={() => setOperation(op.key)}
            >
              {op.label}
            </Button>
          ))}
        </div>
        <div className="section-actions">
          {operation === 'rewrite' && (
            <select
              className="select"
              value={style}
              onChange={(e) => setStyle(e.target.value)}
            >
              {config.styles.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          )}
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
            <label className="panel-label">Original Text</label>
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
            placeholder="Enter your text here..."
          />
        </div>
        <div className="module-panel-right">
          <div className="panel-header">
            <label className="panel-label">Processed Result</label>
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
            placeholder="Result will appear here..."
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
          {loading ? '⏳ Processing...' : '▶️ Process'}
        </Button>
      </div>
    </div>
  )
}
