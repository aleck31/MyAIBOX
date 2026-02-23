import { useState, useEffect, useCallback } from 'react'
import { getDrawConfig } from '../api/client'
import ModelSelector from './ModelSelector'
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

export default function DrawProcessor() {
  const saved = loadState()
  const [config, setConfig] = useState<DrawConfig | null>(null)
  const [prompt, setPrompt] = useState(saved.prompt ?? '')
  const [originalPrompt, setOriginalPrompt] = useState(saved.originalPrompt ?? '')
  const [negative, setNegative] = useState(saved.negative ?? '')
  const [style, setStyle] = useState(saved.style ?? '增强(enhance)')
  const [ratio, setRatio] = useState(saved.ratio ?? '1:1')
  const [seed, setSeed] = useState<number>(saved.seed ?? 0)
  const [randomSeed, setRandomSeed] = useState(saved.randomSeed ?? true)
  const [modelId, setModelId] = useState(saved.modelId ?? '')
  const [imageUrl, setImageUrl] = useState<string | null>(saved.imageUrl ?? null)
  const [loading, setLoading] = useState(false)
  const [optimizing, setOptimizing] = useState(false)

  useEffect(() => {
    saveState({ prompt, originalPrompt, negative, style, ratio, seed, randomSeed, modelId, imageUrl })
  }, [prompt, originalPrompt, negative, style, ratio, seed, randomSeed, modelId, imageUrl])

  useEffect(() => {
    getDrawConfig().then((cfg) => {
      setConfig(cfg)
      if (!modelId && cfg.models.length) setModelId(cfg.models[0].model_id)
    })
  }, [])

  // Track original prompt
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
        body: JSON.stringify({ prompt: src, style }),
      })
      const data = await res.json()
      if (data.prompt) setPrompt(data.prompt)
      if (data.negative_prompt) setNegative(data.negative_prompt)
    } catch (err) {
      console.error(err)
    } finally {
      setOptimizing(false)
    }
  }, [originalPrompt, prompt, style, optimizing])

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
          seed, random_seed: randomSeed, model_id: modelId,
        }),
      })
      const data = await res.json()
      if (data.ok) {
        setImageUrl(data.url)
        setSeed(data.seed)
      } else {
        alert(data.error || 'Failed to generate image')
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [prompt, negative, style, ratio, seed, randomSeed, modelId, loading])

  const handleClear = useCallback(() => {
    setPrompt('')
    setOriginalPrompt('')
    setNegative('')
    setImageUrl(null)
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

  return (
    <div className="draw-processor">
      {/* Top bar */}
      <div className="module-options-bar">
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>
          Draw something interesting...
        </span>
        <div className="text-options">
          <ModelSelector models={config.models} value={modelId} onChange={setModelId} />
        </div>
      </div>

      {/* Main content */}
      <div className="draw-main">
        {/* Left: Input */}
        <div className="draw-input-panel">
          <label className="text-panel-label">Prompt</label>
          <textarea
            className="text-area"
            value={prompt}
            onChange={(e) => handlePromptChange(e.target.value)}
            placeholder="Describe what you want to draw..."
            rows={3}
          />

          <label className="text-panel-label">Negative Prompt</label>
          <textarea
            className="text-area"
            value={negative}
            onChange={(e) => setNegative(e.target.value)}
            placeholder="What you don't want in the image..."
            rows={2}
          />

          {/* Options */}
          <div className="draw-options">
            <div className="draw-option-row">
              <select className="top-bar-select" value={style} onChange={(e) => setStyle(e.target.value)}>
                {config.styles.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <select className="top-bar-select" value={ratio} onChange={(e) => setRatio(e.target.value)}>
                {config.ratios.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="draw-option-row">
              <input
                type="number"
                className="draw-seed-input"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
                disabled={randomSeed}
                placeholder="Seed"
              />
              <label className="draw-checkbox-label">
                <input type="checkbox" checked={randomSeed} onChange={(e) => setRandomSeed(e.target.checked)} />
                🎲 Random
              </label>
            </div>
          </div>
        </div>

        {/* Right: Output */}
        <div className="draw-output-panel">
          {imageUrl ? (
            <img src={imageUrl} alt="Generated" className="draw-output-img" />
          ) : loading ? (
            <div className="draw-output-placeholder">
              <div className="spinner-ring" />
              <span>Generating...</span>
            </div>
          ) : (
            <div className="draw-output-placeholder">Generated image will appear here</div>
          )}
        </div>
      </div>

      {/* Bottom actions */}
      <div className="text-actions">
        <button className="text-btn text-btn--secondary" onClick={handleClear}>
          🗑️ Clear
        </button>
        <button
          className="text-btn text-btn--secondary"
          onClick={handleOptimize}
          disabled={optimizing || !prompt.trim()}
        >
          {optimizing ? '⏳ Optimizing...' : '✨ Optimize'}
        </button>
        <button
          className="text-btn text-btn--primary"
          onClick={handleGenerate}
          disabled={loading || !prompt.trim()}
        >
          {loading ? '⏳ Drawing...' : '🪄 Draw'}
        </button>
      </div>
    </div>
  )
}
