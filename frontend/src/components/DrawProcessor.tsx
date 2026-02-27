import { useState, useEffect, useCallback, useRef } from 'react'
import { getDrawConfig } from '../api/client'
import ModelSelector from './ModelSelector'
import ResizablePreview from './ResizablePreview'
import type { DrawConfig } from '../types/draw'

const STORAGE_KEY = 'draw-processor-state'

function loadState() {
  try {
    const s = sessionStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : {}
  } catch { return {} }
}

function saveState(state: Record<string, unknown>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

type Mode = 'generate' | 'edit'

export default function DrawProcessor() {
  const saved = loadState()
  const [config, setConfig] = useState<DrawConfig | null>(null)
  const [mode, setMode] = useState<Mode>(saved.mode ?? 'generate')
  const [prompt, setPrompt] = useState(saved.prompt ?? '')
  const [originalPrompt, setOriginalPrompt] = useState(saved.originalPrompt ?? '')
  const [negative, setNegative] = useState(saved.negative ?? '')
  const [style, setStyle] = useState(saved.style ?? '增强(enhance)')
  const [ratio, setRatio] = useState(saved.ratio ?? '1:1')
  const [seed, setSeed] = useState<number>(saved.seed ?? 0)
  const [randomSeed, setRandomSeed] = useState(saved.randomSeed ?? true)
  const [modelId, setModelId] = useState(saved.modelId ?? '')
  const [resolution, setResolution] = useState(saved.resolution ?? '1K')
  const [imageUrl, setImageUrl] = useState<string | null>(saved.imageUrl ?? null)
  const [editImageUrl, setEditImageUrl] = useState<string | null>(saved.editImageUrl ?? null)
  const [editFile, setEditFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [optimizing, setOptimizing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    saveState({ prompt, originalPrompt, negative, style, ratio, seed, randomSeed, modelId, resolution, imageUrl, editImageUrl, mode })
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
      const res = await fetch('/api/draw/optimize', {
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
    try {
      const res = await fetch('/api/draw/generate', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt, negative_prompt: negative, style, ratio,
          seed, random_seed: randomSeed, model_id: modelId, resolution,
        }),
      })
      const data = await res.json()
      if (data.ok) {
        setImageUrl(data.url)
        setSeed(data.seed)
      } else {
        alert(data.error || 'Failed to generate image')
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Network error')
    } finally {
      setLoading(false)
    }
  }, [prompt, negative, style, ratio, seed, randomSeed, modelId, resolution, loading])

  const handleEdit = useCallback(async () => {
    if (!prompt.trim() || loading || (!editFile && !editImageUrl)) return
    setLoading(true)
    setImageUrl(null)
    try {
      let file = editFile
      // If editing from a generated image URL (no local file), fetch it
      if (!file && editImageUrl) {
        const resp = await fetch(editImageUrl, { credentials: 'include' })
        const blob = await resp.blob()
        file = new window.File([blob], 'edit.png', { type: 'image/png' })
      }
      if (!file) return

      const form = new FormData()
      form.append('image', file)
      form.append('prompt', prompt)
      form.append('model_id', modelId)
      form.append('ratio', ratio)
      form.append('resolution', resolution)

      const res = await fetch('/api/draw/edit', {
        method: 'POST',
        credentials: 'include',
        body: form,
      })
      const data = await res.json()
      if (data.ok) {
        setImageUrl(data.url)
      } else {
        alert(data.error || 'Failed to edit image')
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Network error')
    } finally {
      setLoading(false)
    }
  }, [prompt, editFile, editImageUrl, modelId, ratio, resolution, loading])

  const handleEditFromGenerated = useCallback(() => {
    if (!imageUrl) return
    setMode('edit')
    setEditImageUrl(imageUrl)
    setEditFile(null)
    setPrompt('')
    setOriginalPrompt('')
    setImageUrl(null)
  }, [imageUrl])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setEditFile(file)
    setEditImageUrl(URL.createObjectURL(file))
  }, [])

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
  const canSubmit = prompt.trim() && !loading && (isEdit ? !!editImageUrl : true)

  return (
    <div className="draw-processor">
      {/* Top bar */}
      <div className="module-options-bar">
        <div className="draw-mode-tabs">
          <button className={`draw-mode-tab ${!isEdit ? 'active' : ''}`} onClick={() => setMode('generate')}>🎨 Generate</button>
          <button className={`draw-mode-tab ${isEdit ? 'active' : ''}`} onClick={() => setMode('edit')}>✏️ Edit</button>
        </div>
        <div className="text-options">
          <ModelSelector models={config.models} value={modelId} onChange={setModelId} />
        </div>
      </div>

      {/* Main content */}
      <div className="draw-main">
        {/* Left: Input */}
        <div className="draw-input-panel">
          {/* Edit mode: image upload area */}
          {isEdit && (
            <div className="draw-edit-source">
              <label className="text-panel-label">Source Image</label>
              {editImageUrl ? (
                <ResizablePreview height="50%" minHeight={200} className="draw-edit-source-preview">
                  <img src={editImageUrl} alt="Source" className="file-preview-img" />
                  <button className="draw-action-btn" style={{ position: 'absolute', top: 4, right: 4 }} onClick={() => { setEditImageUrl(null); setEditFile(null) }} title="Remove">✕</button>
                </ResizablePreview>
              ) : (
                <div className="draw-edit-upload" onClick={() => fileInputRef.current?.click()}>
                  <span>📁 Click or drag image here</span>
                  <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={handleFileSelect} />
                </div>
              )}
            </div>
          )}

          <label className="text-panel-label">{isEdit ? 'Edit Instruction' : 'Prompt'}</label>
          <textarea
            className="text-area"
            value={prompt}
            onChange={(e) => handlePromptChange(e.target.value)}
            placeholder={isEdit ? 'Describe what to change...' : 'Describe what you want to draw...'}
            rows={3}
          />

          {!isEdit && (
            <>
              <label className="text-panel-label">Negative Prompt</label>
              <textarea
                className="text-area"
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
              <select className="top-bar-select" value={ratio} onChange={(e) => setRatio(e.target.value)}>
                {config.ratios.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <select className="top-bar-select" value={resolution} onChange={(e) => setResolution(e.target.value)}>
                {config.resolutions?.map((r: string) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            {!isEdit && (
              <div className="draw-option-row">
                <select className="top-bar-select" value={style} onChange={(e) => setStyle(e.target.value)}>
                  {config.styles.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <label className="draw-checkbox-label">
                  <input type="checkbox" checked={randomSeed} onChange={(e) => setRandomSeed(e.target.checked)} />
                  🎲 Random
                </label>
                <input
                  type="number"
                  className="draw-seed-input"
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
        <div className="draw-output-panel">
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
            ) : (
              <div className="draw-output-placeholder">{isEdit ? 'Edited image will appear here' : 'Generated image will appear here'}</div>
            )}
          </ResizablePreview>
        </div>
      </div>

      {/* Bottom actions */}
      <div className="text-actions">
        <button className="text-btn text-btn--secondary" onClick={handleClear}>
          🗑️ Clear
        </button>
        {!isEdit && (
          <button
            className="text-btn text-btn--secondary"
            onClick={handleOptimize}
            disabled={optimizing || !prompt.trim()}
          >
            {optimizing ? '⏳ Optimizing...' : '✨ Optimize'}
          </button>
        )}
        <button
          className="text-btn text-btn--primary"
          onClick={isEdit ? handleEdit : handleGenerate}
          disabled={!canSubmit}
        >
          {loading ? (isEdit ? '⏳ Editing...' : '⏳ Drawing...') : (isEdit ? '✏️ Edit' : '🪄 Draw')}
        </button>
      </div>
    </div>
  )
}
