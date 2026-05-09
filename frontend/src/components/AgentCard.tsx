import { useEffect, useMemo, useState } from 'react'
import type { ChatAgent, ChatToolInfo } from '../api/client'

interface ModelOpt { model_id: string; name: string }
interface NameDesc { name: string; description: string }

interface Props {
  agent: ChatAgent
  defaultOpen?: boolean
  models: ModelOpt[]
  legacyTools: ChatToolInfo[]
  builtinTools: ChatToolInfo[]
  mcpServers: string[]
  skills: NameDesc[]
  onSave: (patch: Partial<ChatAgent>) => Promise<void>
  onReset: () => Promise<void>
}

type Params = {
  temperature?: number
  top_p?: number
  top_k?: number
  max_tokens?: number
  stop_sequences?: string[]
}

function snapshot(agent: ChatAgent) {
  return {
    default_model: agent.default_model ?? '',
    legacy: [...agent.enabled_legacy_tools],
    builtin: [...agent.enabled_builtin_tools],
    mcp: [...agent.enabled_mcp_servers],
    skills: [...agent.enabled_skills],
    params: { ...(agent.parameters as Params) },
  }
}

function arrayEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  const sa = [...a].sort()
  const sb = [...b].sort()
  return sa.every((v, i) => v === sb[i])
}

function paramsEqual(a: Params, b: Params): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<keyof Params>
  for (const k of keys) {
    const av = (a as any)[k]
    const bv = (b as any)[k]
    if (Array.isArray(av) && Array.isArray(bv)) {
      if (!arrayEqual(av, bv)) return false
    } else if (av !== bv) return false
  }
  return true
}

export default function AgentCard({
  agent, defaultOpen = false, models, legacyTools, builtinTools, mcpServers, skills,
  onSave, onReset,
}: Props) {
  const [open, setOpen] = useState(defaultOpen)
  const initial = useMemo(() => snapshot(agent), [agent])
  const [state, setState] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Re-sync local form when the agent prop changes (after Save / Reset).
  useEffect(() => { setState(snapshot(agent)); setError(null) }, [agent])

  const dirty = useMemo(() => (
    state.default_model !== initial.default_model
    || !arrayEqual(state.legacy, initial.legacy)
    || !arrayEqual(state.builtin, initial.builtin)
    || !arrayEqual(state.mcp, initial.mcp)
    || !arrayEqual(state.skills, initial.skills)
    || !paramsEqual(state.params, initial.params)
  ), [state, initial])

  const toggle = (list: string[], name: string) => (
    list.includes(name) ? list.filter(x => x !== name) : [...list, name]
  )

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const patch: any = {}
      if (state.default_model !== initial.default_model) {
        patch.default_model = state.default_model || null
      }
      if (!arrayEqual(state.legacy, initial.legacy)) patch.enabled_legacy_tools = state.legacy
      if (!arrayEqual(state.builtin, initial.builtin)) patch.enabled_builtin_tools = state.builtin
      if (!arrayEqual(state.mcp, initial.mcp)) patch.enabled_mcp_servers = state.mcp
      if (!arrayEqual(state.skills, initial.skills)) patch.enabled_skills = state.skills
      if (!paramsEqual(state.params, initial.params)) patch.parameters = state.params
      await onSave(patch)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!confirm(`Reset "${agent.name}" to built-in defaults? This clears your overrides.`)) return
    setResetting(true)
    setError(null)
    try {
      await onReset()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setResetting(false)
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
          <span className="agent-card-avatar">{agent.avatar}</span>
          <span className="settings-module-name">{agent.name}</span>
        </span>
        <span className="agent-card-summary">
          {state.default_model || models[0]?.model_id || '—'}
          <span className="agent-card-chevron" aria-hidden>{open ? '▾' : '▸'}</span>
        </span>
      </button>

      {open && (
        <div className="settings-module-body agent-card-body">
          <p className="agent-card-desc">{agent.description}</p>

          {/* Model */}
          <div className="agent-field">
            <label className="panel-label">Model</label>
            <select
              className="select"
              style={{ width: '100%', maxWidth: 360 }}
              value={state.default_model}
              onChange={(e) => setState(s => ({ ...s, default_model: e.target.value }))}
            >
              <option value="">(module default)</option>
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
                value={state.params.temperature ?? 0.7}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, temperature: v } }))}
              />
              <ParamSlider
                label="Top P" min={0} max={1} step={0.01}
                value={state.params.top_p ?? 0.9}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, top_p: v } }))}
              />
              <ParamNumber
                label="Top K"
                value={state.params.top_k}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, top_k: v } }))}
                min={1} max={500} step={1}
              />
              <ParamNumber
                label="Max tokens"
                value={state.params.max_tokens}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, max_tokens: v } }))}
                min={128} max={32000} step={128}
              />
              <StopSequences
                value={state.params.stop_sequences ?? []}
                onChange={(v) => setState(s => ({ ...s, params: { ...s.params, stop_sequences: v } }))}
              />
            </div>
          </div>

          {/* Legacy tools */}
          <ToggleGroup
            label="Legacy tools"
            items={legacyTools}
            enabled={state.legacy}
            onToggle={(n) => setState(s => ({ ...s, legacy: toggle(s.legacy, n) }))}
          />

          {/* Builtin tools */}
          <ToggleGroup
            label="Strands builtin tools"
            items={builtinTools}
            enabled={state.builtin}
            onToggle={(n) => setState(s => ({ ...s, builtin: toggle(s.builtin, n) }))}
          />

          {/* MCP servers */}
          <ToggleGroup
            label="MCP servers"
            items={mcpServers.map(n => ({ name: n, description: '' }))}
            enabled={state.mcp}
            onToggle={(n) => setState(s => ({ ...s, mcp: toggle(s.mcp, n) }))}
            emptyHint="No MCP servers configured."
          />

          {/* Skills */}
          <ToggleGroup
            label="Skills"
            items={skills}
            enabled={state.skills}
            onToggle={(n) => setState(s => ({ ...s, skills: toggle(s.skills, n) }))}
            emptyHint="No skills installed under ~/.agents/skills/."
          />

          {error && <div className="agent-card-error">{error}</div>}

          <div className="agent-card-actions">
            <button
              className="btn btn--ghost"
              onClick={handleReset}
              disabled={resetting || saving}
              title="Drop your overrides and restore the built-in defaults"
            >
              {resetting ? 'Resetting…' : 'Reset to defaults'}
            </button>
            <button
              className="btn btn--primary"
              onClick={handleSave}
              disabled={!dirty || saving || resetting}
            >
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function ParamSlider({ label, min, max, step, value, onChange }: {
  label: string; min: number; max: number; step: number; value: number;
  onChange: (v: number) => void;
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

function ParamNumber({ label, value, onChange, min, max, step }: {
  label: string; value?: number; onChange: (v: number | undefined) => void;
  min?: number; max?: number; step?: number;
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

function StopSequences({ value, onChange }: {
  value: string[]; onChange: (v: string[]) => void;
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
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); add() }
          }}
          onBlur={add}
        />
      </div>
    </label>
  )
}

function ToggleGroup({ label, items, enabled, onToggle, emptyHint }: {
  label: string;
  items: Array<{ name: string; description: string }>;
  enabled: string[];
  onToggle: (name: string) => void;
  emptyHint?: string;
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
