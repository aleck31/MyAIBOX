import { useState, useEffect, useCallback, useRef } from 'react'
import { authFetch, getVisionConfig } from '../api/client'
import { readSSE } from '../api/sse'
import ModelSelector from './ModelSelector'
import ResizablePreview from './ResizablePreview'
import type { VisionConfig } from '../types/vision'

const STORAGE_KEY = 'vision-processor-state'

function loadState() {
  try {
    const s = sessionStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : {}
  } catch { return {} }
}

function saveState(state: Record<string, unknown>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export default function VisionProcessor() {
  const saved = loadState()
  const [config, setConfig] = useState<VisionConfig | null>(null)
  const [text, setText] = useState(saved.text ?? '')
  const [output, setOutput] = useState(saved.output ?? '')
  const [modelId, setModelId] = useState(saved.modelId ?? '')
  const [files, setFiles] = useState<File[]>([])
  const [preview, setPreview] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    saveState({ text, output, modelId })
  }, [text, output, modelId])

  useEffect(() => {
    getVisionConfig().then((cfg) => {
      setConfig(cfg)
      if (!modelId && cfg.models.length) setModelId(cfg.models[0].model_id)
    })
  }, [])

  // Generate preview URL for image or PDF
  useEffect(() => {
    if (files.length > 0) {
      const url = URL.createObjectURL(files[0])
      setPreview(url)
      return () => URL.revokeObjectURL(url)
    } else {
      setPreview(null)
    }
  }, [files])

  const isPdf = files.length > 0 && files[0].type === 'application/pdf'

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFiles(Array.from(e.target.files))
    }
  }, [])

  const handleAnalyze = useCallback(async () => {
    if (files.length === 0 || loading) return
    setLoading(true)
    setOutput('')

    const formData = new FormData()
    formData.append('text', text)
    formData.append('model_id', modelId)
    files.forEach((f) => formData.append('files', f))

    try {
      const res = await authFetch('/api/vision/analyze', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      })

      let result = ''
      await readSSE(res, {
        onText: (delta) => { result += delta; setOutput(result) },
        onError: (msg) => setOutput(msg),
      })
    } catch (err) {
      setOutput('An error occurred during analysis.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [text, modelId, files, loading])

  const handleClear = useCallback(() => {
    setText('')
    setOutput('')
    setFiles([])
    setPreview(null)
    sessionStorage.removeItem(STORAGE_KEY)
  }, [])

  const handleCopy = useCallback((t: string) => {
    navigator.clipboard.writeText(t)
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
    <div className="split-panel">
      {/* Top bar */}
      <div className="module-options-bar">
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>
          I can see 乛◡乛
        </span>
        <div className="text-options">
          <ModelSelector models={config.models} value={modelId} onChange={setModelId} />
        </div>
      </div>

      {/* Main content */}
      <div className="split-panel-main">
        {/* Left: Input */}
        <div className="split-panel-left">
          {/* File preview */}
          <ResizablePreview minHeight={200}>
            {preview && isPdf ? (
              <iframe src={preview} className="file-preview-iframe" title="PDF Preview" />
            ) : preview ? (
              <img src={preview} alt="Preview" className="file-preview-img" />
            ) : (
              <div className="file-preview-placeholder">No file selected</div>
            )}
          </ResizablePreview>

          {/* Input area */}
          <div className="split-panel-fill">
            <div className="attach-file-row">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,.pdf"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
              <button
                className="text-btn text-btn--secondary"
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                📎 Select Image or PDF
              </button>
              {files.length > 0 && (
                <button
                  className="text-btn text-btn--secondary"
                  onClick={() => { setFiles([]); setPreview(null) }}
                  type="button"
                >
                  ✕
                </button>
              )}
            </div>

            <label className="text-panel-label">
              What would you like me to analyze?
            </label>
            <textarea
              className="text-area"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Describe what you want me to look for, or leave empty for general analysis..."
            />
          </div>
        </div>

        {/* Right: Output */}
        <div className="split-panel-right">
          <div className="text-panel-header">
            <label className="text-panel-label">Analysis Results</label>
            {output && (
              <button className="aui-action-bar-button" onClick={() => handleCopy(output)} title="Copy">
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="5" y="5" width="9" height="9" rx="1.5" />
                  <path d="M10 5V3.5A1.5 1.5 0 008.5 2h-5A1.5 1.5 0 002 3.5v5A1.5 1.5 0 003.5 10H5" />
                </svg>
              </button>
            )}
          </div>
          <div className="vision-output-content">
            {output || 'Analysis results will appear here...'}
          </div>
        </div>
      </div>

      {/* Bottom actions */}
      <div className="text-actions">
        <button className="text-btn text-btn--secondary" onClick={handleClear}>
          🗑️ Clear
        </button>
        <button
          className="text-btn text-btn--primary"
          onClick={handleAnalyze}
          disabled={loading || files.length === 0}
        >
          {loading ? '🔍 Analyzing...' : '▶️ Analyze'}
        </button>
      </div>
    </div>
  )
}
