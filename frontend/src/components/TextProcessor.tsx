import { useState, useEffect, useCallback } from 'react'
import { authFetch, getTextConfig } from '../api/client'
import { readSSE } from '../api/sse'
import { Button } from './Button'
import {
  IconTrash,
  IconSpellCheck,
  IconReplace,
  IconScissors,
  IconExpand,
} from './icons'
import type { LucideProps } from 'lucide-react'

// Operation key → icon. Backend owns the label text, frontend owns the visual.
const OPERATION_ICONS: Record<string, React.ComponentType<LucideProps>> = {
  proofread: IconSpellCheck,
  rewrite: IconReplace,
  reduce: IconScissors,
  expand: IconExpand,
}
import ModelSelector from './ModelSelector'
import { useStoredState } from '../hooks/useStoredState'
import { resolveDefaultModel } from '../utils/model'
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
  // Model preference persists across tabs/reopens (localStorage).
  const [modelId, setModelId] = useStoredState<string>('text-model', '')
  const [loading, setLoading] = useState(false)

  // Persist state on change
  useEffect(() => {
    saveState({ input, output, operation, targetLang, style })
  }, [input, output, operation, targetLang, style])

  useEffect(() => {
    getTextConfig().then((cfg) => {
      setConfig(cfg)
      if (!modelId && cfg.models?.length) setModelId(resolveDefaultModel(cfg.models, cfg.default_model))
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
        <div className="segmented" role="tablist" aria-label="Operation">
          {config.operations.map((op) => {
            const Icon = OPERATION_ICONS[op.key]
            return (
              <button
                key={op.key}
                type="button"
                role="tab"
                aria-selected={operation === op.key}
                className={`segmented-item${operation === op.key ? ' is-active' : ''}`}
                onClick={() => setOperation(op.key)}
              >
                {Icon && <Icon size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />}
                {op.label}
              </button>
            )
          })}
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
        <Button onClick={handleClear}><IconTrash size={14} style={{ marginRight: 4 }} />Clear</Button>
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
