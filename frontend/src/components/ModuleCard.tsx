import { useEffect, useMemo, useState } from 'react'
import type { ModuleConfig } from '../types/settings'
import { ParamSlider, ParamNumber, StopSequences, ToggleGroup, arrayEqual } from './settings/FormControls'

interface ModelOpt { model_id: string; name: string }

interface Props {
  name: string
  config: ModuleConfig
  defaultOpen?: boolean
  models: ModelOpt[]
  availableTools: string[]
  onSave: (patch: ModuleConfig) => Promise<void>
}

type Params = {
  temperature?: number
  top_p?: number
  top_k?: number
  max_tokens?: number
  stop_sequences?: string[]
  // Some modules carry extra keys (e.g. summary has style-specific params).
  // Preserve them untouched so we don't drop config we don't have a UI for.
  [key: string]: unknown
}

/** Parse the JSON string the backend sends; recover gracefully on bad input. */
function parseParams(raw: string): Params {
  if (!raw) return {}
  try {
    const obj = JSON.parse(raw)
    return obj && typeof obj === 'object' ? obj : {}
  } catch {
    return {}
  }
}

function snapshot(cfg: ModuleConfig) {
  return {
    default_model: cfg.default_model,
    enabled_tools: [...cfg.enabled_tools],
    params: parseParams(cfg.parameters) as Params,
  }
}

function paramsEqual(a: Params, b: Params): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)])
  for (const k of keys) {
    const av = (a as any)[k]
    const bv = (b as any)[k]
    if (Array.isArray(av) && Array.isArray(bv)) {
      if (!arrayEqual(av, bv)) return false
    } else if (av !== bv) return false
  }
  return true
}

export default function ModuleCard({ name, config, defaultOpen = false, models, availableTools, onSave }: Props) {
  const [open, setOpen] = useState(defaultOpen)
  const initial = useMemo(() => snapshot(config), [config])
  const [state, setState] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { setState(snapshot(config)); setError(null) }, [config])

  const dirty = useMemo(() => (
    state.default_model !== initial.default_model
    || !arrayEqual(state.enabled_tools, initial.enabled_tools)
    || !paramsEqual(state.params, initial.params)
  ), [state, initial])

  const toggle = (list: string[], name: string) => (
    list.includes(name) ? list.filter(x => x !== name) : [...list, name]
  )

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await onSave({
        default_model: state.default_model,
        enabled_tools: state.enabled_tools,
        parameters: JSON.stringify(state.params, null, 2),
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="settings-module-card">
      <button
        type="button"
        className="settings-module-header agent-card-header"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className="agent-card-title">
          <span className="settings-module-name">{name}</span>
        </span>
        <span className="agent-card-summary">
          {state.default_model || '—'}
          <span className="agent-card-chevron" aria-hidden>{open ? '▾' : '▸'}</span>
        </span>
      </button>

      {open && (
        <div className="settings-module-body agent-card-body">
          {/* Model */}
          <div className="agent-field">
            <label className="panel-label">Model</label>
            <select
              className="select"
              style={{ width: '100%', maxWidth: 360 }}
              value={state.default_model}
              onChange={(e) => setState(s => ({ ...s, default_model: e.target.value }))}
            >
              <option value="">— None —</option>
              {models.map(m => (
                <option key={m.model_id} value={m.model_id}>{m.name}</option>
              ))}
            </select>
          </div>

          {/* Parameters */}
          <div className="agent-field">
            <label className="panel-label">Parameters</label>
            <div className="agent-params-grid">
              <ParamSlider
                label="Temperature" min={0} max={1} step={0.05}
                value={(state.params.temperature as number | undefined) ?? 0.7}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, temperature: v } }))}
              />
              <ParamSlider
                label="Top P" min={0} max={1} step={0.01}
                value={(state.params.top_p as number | undefined) ?? 0.9}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, top_p: v } }))}
              />
              <ParamNumber
                label="Top K"
                value={state.params.top_k as number | undefined}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, top_k: v } }))}
                min={1} max={500} step={1}
              />
              <ParamNumber
                label="Max tokens"
                value={state.params.max_tokens as number | undefined}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, max_tokens: v } }))}
                min={128} max={32000} step={128}
              />
              <StopSequences
                value={(state.params.stop_sequences as string[] | undefined) ?? []}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, stop_sequences: v } }))}
              />
            </div>
          </div>

          {/* Enabled tools (legacy — tool modules only ship legacy tools) */}
          <ToggleGroup
            label="Enabled tools"
            items={availableTools.map(t => ({ name: t, description: '' }))}
            enabled={state.enabled_tools}
            onToggle={(n) => setState(s => ({ ...s, enabled_tools: toggle(s.enabled_tools, n) }))}
            emptyHint="No tools registered."
          />

          {error && <div className="agent-card-error">{error}</div>}

          <div className="agent-card-actions">
            <button
              className="btn btn--primary"
              onClick={handleSave}
              disabled={!dirty || saving}
            >
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
