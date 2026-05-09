import { useState } from 'react'

/** A labelled range slider with a numeric readout. */
export function ParamSlider({ label, min, max, step, value, onChange }: {
  label: string
  min: number
  max: number
  step: number
  value: number
  onChange: (v: number) => void
}) {
  return (
    <label className="agent-param">
      <span className="agent-param-label">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
      <span className="agent-param-value">{value.toFixed(2)}</span>
    </label>
  )
}

/** A labelled integer input (no value when undefined). */
export function ParamNumber({ label, value, onChange, min, max, step }: {
  label: string
  value?: number
  onChange: (v: number | undefined) => void
  min?: number
  max?: number
  step?: number
}) {
  return (
    <label className="agent-param">
      <span className="agent-param-label">{label}</span>
      <input
        type="number"
        className="input"
        style={{ width: 100 }}
        value={value ?? ''}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const raw = e.target.value
          onChange(raw === '' ? undefined : parseInt(raw, 10))
        }}
      />
    </label>
  )
}

/** A tag-input for string lists (stop sequences, custom keywords, etc.). */
export function StopSequences({ value, onChange }: {
  value: string[]
  onChange: (v: string[]) => void
}) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const t = draft.trim()
    if (!t || value.includes(t)) return
    onChange([...value, t])
    setDraft('')
  }
  return (
    <label className="agent-param agent-param-stop">
      <span className="agent-param-label">Stop sequences</span>
      <div className="agent-stop-tags">
        {value.map(v => (
          <span key={v} className="agent-stop-tag">
            {v}
            <button
              type="button"
              className="agent-stop-tag-remove"
              onClick={() => onChange(value.filter(x => x !== v))}
              title={`Remove ${v}`}
            >×</button>
          </span>
        ))}
        <input
          className="input"
          style={{ width: 120 }}
          placeholder="add…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          onBlur={add}
        />
      </div>
    </label>
  )
}

/** A grid of checkbox toggles with hover descriptions. */
export function ToggleGroup({ label, items, enabled, onToggle, emptyHint }: {
  label: string
  items: Array<{ name: string; description: string }>
  enabled: string[]
  onToggle: (name: string) => void
  emptyHint?: string
}) {
  return (
    <div className="agent-field">
      <label className="panel-label">{label}</label>
      {items.length === 0 ? (
        <span className="agent-empty-hint">{emptyHint || '(none available)'}</span>
      ) : (
        <div className="agent-toggle-grid">
          {items.map(it => (
            <label key={it.name} className="agent-toggle" title={it.description || it.name}>
              <input
                type="checkbox"
                checked={enabled.includes(it.name)}
                onChange={() => onToggle(it.name)}
              />
              <span>{it.name}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

export function arrayEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  const sa = [...a].sort()
  const sb = [...b].sort()
  return sa.every((v, i) => v === sb[i])
}
