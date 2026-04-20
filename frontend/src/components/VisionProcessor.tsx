import { useState, useEffect, useCallback } from 'react'
import { authFetch, getVisionConfig } from '../api/client'
import { readSSE } from '../api/sse'
import { Button } from './Button'
import ModelSelector from './ModelSelector'
import FilePreviewPanel from './FilePreviewPanel'
import type { VisionConfig } from '../types/vision'

const STORAGE_KEY = 'vision-processor-state'

function loadState() {
  try {
    const s = sessionStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : {}
  } catch { return {} }
}

function saveState(state: Record<string, unknown>) {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state)) } catch { /* quota exceeded */ }
}

export default function VisionProcessor() {
  const saved = loadState()
  const [config, setConfig] = useState<VisionConfig | null>(null)
  const [text, setText] = useState(saved.text ?? '')
  const [output, setOutput] = useState(saved.output ?? '')
  const [modelId, setModelId] = useState(saved.modelId ?? '')
  const [files, setFiles] = useState<File[]>([])
  const [previewUrl, setPreviewUrl] = useState<string | null>(saved.previewUrl ?? null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    saveState({ text, output, modelId, previewUrl })
  }, [text, output, modelId, previewUrl])

  useEffect(() => {
    getVisionConfig().then((cfg) => {
      setConfig(cfg)
      if (!modelId && cfg.models.length) setModelId(cfg.models[0].model_id)
    })
  }, [])

  const handleAnalyze = useCallback(async () => {
    if (loading || (files.length === 0 && !previewUrl)) return
    setLoading(true)
    setOutput('')

    const formData = new FormData()
    formData.append('text', text)
    formData.append('model_id', modelId)
    if (files.length > 0) {
      files.forEach((f) => formData.append('files', f))
    } else if (previewUrl) {
      formData.append('existing_files', previewUrl)
    }

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
        onMetadata: (data) => {
          const urls = data.file_urls as string[]
          if (urls?.[0]) setPreviewUrl(urls[0])
        },
      })
    } catch (err) {
      setOutput('An error occurred during analysis.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [text, modelId, files, previewUrl, loading])

  const handleClear = useCallback(() => {
    setText('')
    setOutput('')
    setFiles([])
    setPreviewUrl(null)
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
    <div className="module-layout">
      {/* Top bar */}
      <div className="module-options-bar">
        <div className="module-options">
          <ModelSelector models={config.models} value={modelId} onChange={setModelId} />
        </div>
      </div>

      {/* Main content */}
      <div className="module-panel-main">
        {/* Left: Input */}
        <div className="module-panel-left">
          <FilePreviewPanel
            accept="image/*,.pdf"
            label="File Preview"
            placeholder="Select Image or PDF"
            externalUrl={previewUrl}
            minHeight={200}
            onFileChange={(f) => {
              setFiles(f ? [f] : [])
              if (!f) setPreviewUrl(null)
            }}
            onClear={() => setPreviewUrl(null)}
          />

          {/* Input area */}
          <div className="module-panel-fill">
            <label className="panel-label">
              What would you like me to analyze?
            </label>
            <textarea
              className="panel-textarea"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Describe what you want me to look for, or leave empty for general analysis..."
            />
          </div>
        </div>

        {/* Right: Output */}
        <div className="module-panel-right">
          <div className="panel-header">
            <label className="panel-label">Analysis Results</label>
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
      <div className="module-action-bar">
        <Button onClick={handleClear}>🗑️ Clear</Button>
        <Button
          variant="primary"
          onClick={handleAnalyze}
          disabled={loading || (files.length === 0 && !previewUrl)}
        >
          {loading ? '🔍 Analyzing...' : '▶️ Analyze'}
        </Button>
      </div>
    </div>
  )
}
