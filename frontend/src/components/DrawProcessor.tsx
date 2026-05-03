import { useState, useEffect, useCallback } from 'react'
import { authFetch, getDrawConfig } from '../api/client'
import { Button } from './Button'
import ModelSelector from './ModelSelector'
import ResizablePreview from './ResizablePreview'
import FilePreviewPanel from './FilePreviewPanel'
import type { DrawConfig } from '../types/draw'

const STORAGE_KEY = 'draw-processor-state'

function loadState() {
  try {
    const s = sessionStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : {}
  } catch { return {} }
}

function saveState(state: Record<string, unknown>) {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state)) } catch { /* quota exceeded */ }
}

type Mode = 'generate' | 'edit'

export default function DrawProcessor() {
  const saved = loadState()
  const [config, setConfig] = useState<DrawConfig | null>(null)
  const [mode, setMode] = useState<Mode>(saved.mode ?? 'generate')
  const [prompt, setPrompt] = useState(saved.prompt ?? '')
  const [originalPrompt, setOriginalPrompt] = useState(saved.originalPrompt ?? '')
  const [editPrompt, setEditPrompt] = useState(saved.editPrompt ?? '')
  const [negative, setNegative] = useState(saved.negative ?? '')
  const [style, setStyle] = useState(saved.style ?? '增强(enhance)')
  const [ratio, setRatio] = useState(saved.ratio ?? '1:1')
  const [seed, setSeed] = useState<number>(saved.seed ?? 0)
  const [randomSeed, setRandomSeed] = useState(saved.randomSeed ?? true)
  const [modelId, setModelId] = useState(saved.modelId ?? '')
  const [resolution, setResolution] = useState(saved.resolution ?? '1K')
  const [temperature, setTemperature] = useState(saved.temperature ?? 0.6)
  const [imageUrl, setImageUrl] = useState<string | null>(saved.imageUrl ?? null)
  const [editImageUrl, setEditImageUrl] = useState<string | null>(saved.editImageUrl ?? null)
  const [editFile, setEditFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [optimizing, setOptimizing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    saveState({ prompt, originalPrompt, editPrompt, negative, style, ratio, seed, randomSeed, modelId, resolution, imageUrl, editImageUrl, mode, temperature })
  }, [prompt, originalPrompt, negative, style, ratio, seed, randomSeed, modelId, resolution, imageUrl, editImageUrl, mode])

  useEffect(() => {
    getDrawConfig().then((cfg) => {
      setConfig(cfg)
      if (!modelId && cfg.models.length) setModelId(cfg.models[0].model_id)
    })
  }, [])

  const handlePromptChange = useCallback((val: string) => {
    setPrompt(val)
    setOriginalPrompt(val)
  }, [])

  const handleOptimize = useCallback(async () => {
    const src = originalPrompt || prompt
    if (!src.trim() || optimizing) return
    setOptimizing(true)
    try {
      const res = await authFetch('/api/draw/optimize', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: src, style, model_id: modelId }),
      })
      const data = await res.json()
      if (data.prompt) setPrompt(data.prompt)
      if (data.negative_prompt) setNegative(data.negative_prompt)
    } catch (err) {
      console.error(err)
    } finally {
      setOptimizing(false)
    }
  }, [originalPrompt, prompt, style, modelId, optimizing])

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim() || loading) return
    setLoading(true)
    setImageUrl(null)
    setError(null)
    try {
      const res = await authFetch('/api/draw/generate', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt, negative_prompt: negative, style, ratio,
          seed, random_seed: randomSeed, model_id: modelId, resolution, temperature,
        }),
      })
      const data = await res.json()
      if (data.ok) {
        setImageUrl(data.url)
        setSeed(data.seed)
      } else {
        setError(data.error || 'Failed to generate image')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Network error')
    } finally {
      setLoading(false)
    }
  }, [prompt, negative, style, ratio, seed, randomSeed, modelId, resolution, loading])

  const handleEdit = useCallback(async () => {
    if (!editPrompt.trim() || loading || (!editFile && !editImageUrl)) return
    setLoading(true)
    setImageUrl(null)
    setError(null)
    try {
      const form = new FormData()
      if (editFile) {
        form.append('image', editFile)
      } else if (editImageUrl) {
        form.append('image_url', editImageUrl)
      } else {
        return
      }
      form.append('prompt', editPrompt)
      form.append('model_id', modelId)
      form.append('ratio', ratio)
      form.append('resolution', resolution)
      form.append('temperature', String(temperature))

      const res = await authFetch('/api/draw/edit', {
        method: 'POST',
        credentials: 'include',
        body: form,
      })
      const data = await res.json()
      if (data.ok) {
        setImageUrl(data.url)
        if (data.source_url) setEditImageUrl(data.source_url)
      } else {
        setError(data.error || 'Failed to edit image')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Network error')
    } finally {
      setLoading(false)
    }
  }, [editPrompt, editFile, editImageUrl, modelId, ratio, resolution, loading])

  const handleEditFromGenerated = useCallback(() => {
    if (!imageUrl) return
    setMode('edit')
    setEditImageUrl(imageUrl)
    setEditFile(null)
    setPrompt('')
    setOriginalPrompt('')
    setImageUrl(null)
  }, [imageUrl])

  const handleClear = useCallback(() => {
    setPrompt('')
    setOriginalPrompt('')
    setNegative('')
    setImageUrl(null)
    setEditImageUrl(null)
    setEditFile(null)
    sessionStorage.removeItem(STORAGE_KEY)
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

  const isEdit = mode === 'edit'
  const canSubmit = !loading && (isEdit ? editPrompt.trim() && !!(editFile || editImageUrl) : !!prompt.trim())

  return (
    <div className="module-layout">
      {/* Top bar */}
      <div className="section-bar">
        <div className="draw-mode-tabs">
          <button className={`draw-mode-tab ${!isEdit ? 'active' : ''}`} onClick={() => setMode('generate')}>🎨 Generate</button>
          <button className={`draw-mode-tab ${isEdit ? 'active' : ''}`} onClick={() => setMode('edit')}>✏️ Edit</button>
        </div>
        <div className="section-actions">
          <ModelSelector models={isEdit ? config.edit_models : config.models} value={modelId} onChange={setModelId} />
        </div>
      </div>

      {/* Main content */}
      <div className="module-panel-main">
        {/* Left: Input */}
        <div className="module-panel-left module-panel-left--scroll">
          {/* Edit mode: image upload area */}
          {isEdit && (
            <FilePreviewPanel
              accept="image/*"
              label="Source Image"
              externalUrl={editImageUrl}
              minHeight={120}
              onFileChange={(f) => {
                setEditFile(f)
                if (!f) setEditImageUrl(null)
              }}
              onClear={() => setEditImageUrl(null)}
              className="draw-edit-source"
            />
          )}

          {isEdit ? (
            <div className="module-panel-fill">
              <label className="panel-label">Edit Instruction</label>
              <textarea
                className="panel-textarea"
                style={{ minHeight: 100 }}
                value={editPrompt}
                onChange={(e) => setEditPrompt(e.target.value)}
                placeholder="Describe what to change..."
              />
            </div>
          ) : (
            <>
              <label className="panel-label">Prompt</label>
              <textarea
                className="panel-textarea"
                value={prompt}
                onChange={(e) => handlePromptChange(e.target.value)}
                placeholder="Describe what you want to draw..."
                rows={3}
              />
            </>
          )}

          {!isEdit && (
            <>
              <label className="panel-label">Negative Prompt</label>
              <textarea
                className="panel-textarea"
                value={negative}
                onChange={(e) => setNegative(e.target.value)}
                placeholder="What you don't want in the image..."
                rows={2}
              />
            </>
          )}

          {/* Options */}
          <div className="draw-options">
            <div className="draw-option-row">
              <select className="select" value={ratio} onChange={(e) => setRatio(e.target.value)}>
                {config.ratios.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <select className="select" value={resolution} onChange={(e) => setResolution(e.target.value)}>
                {config.resolutions?.map((r: string) => <option key={r} value={r}>{r}</option>)}
              </select>
              <label className="draw-temp-label">
                🌡️ {temperature.toFixed(1)}
                <input type="range" min="0" max="1" step="0.1" value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} />
              </label>
            </div>
            {!isEdit && (
              <div className="draw-option-row">
                <select className="select" value={style} onChange={(e) => setStyle(e.target.value)}>
                  {config.styles.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <label className="draw-checkbox-label">
                  <input type="checkbox" checked={randomSeed} onChange={(e) => setRandomSeed(e.target.checked)} />
                  🎲 Random
                </label>
                <input
                  type="number"
                  className="input"
                  style={{ width: 120 }}
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value))}
                  disabled={randomSeed}
                  placeholder="Seed"
                />
              </div>
            )}
          </div>
        </div>

        {/* Right: Output */}
        <div className="module-panel-right">
          <div className="panel-header">
            <label className="panel-label">{isEdit ? 'Edited Image' : 'Generated Image'}</label>
          </div>
          <ResizablePreview minHeight={200}>
            {imageUrl ? (
              <>
                <img src={imageUrl} alt="Generated" className="file-preview-img" />
                <div className="draw-output-actions">
                  <a href={imageUrl} download className="draw-action-btn" title="Download">
                    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10 3v10m0 0l-3.5-3.5M10 13l3.5-3.5M3 17h14"/>
                    </svg>
                  </a>
                  <button className="draw-action-btn" onClick={handleEditFromGenerated} title="Edit this image">
                    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M13.5 3.5l3 3L7 16H4v-3L13.5 3.5z"/>
                    </svg>
                  </button>
                </div>
              </>
            ) : loading ? (
              <div className="draw-output-placeholder">
                <div className="spinner-ring" />
                <span>{isEdit ? 'Editing...' : 'Generating...'}</span>
              </div>
            ) : error ? (
              <div className="draw-output-placeholder draw-error">{error}</div>
            ) : (
              <div className="draw-output-placeholder">{isEdit ? 'Edited image will appear here' : 'Generated image will appear here'}</div>
            )}
          </ResizablePreview>
        </div>
      </div>

      {/* Bottom actions */}
      <div className="module-action-bar">
        <Button onClick={handleClear}>🗑️ Clear</Button>
        {!isEdit && (
          <Button
            onClick={handleOptimize}
            disabled={optimizing || !prompt.trim()}
          >
            {optimizing ? '⏳ Optimizing...' : '✨ Optimize'}
          </Button>
        )}
        <Button
          variant="primary"
          onClick={isEdit ? handleEdit : handleGenerate}
          disabled={!canSubmit}
        >
          {loading ? (isEdit ? '⏳ Editing...' : '⏳ Drawing...') : (isEdit ? '✏️ Edit' : '🪄 Draw')}
        </Button>
      </div>
    </div>
  )
}
