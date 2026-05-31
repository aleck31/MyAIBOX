import { useEffect, useMemo, useState } from 'react'
import type { TalkAgent, ChatToolInfo } from '../api/client'
import { ToggleGroup, arrayEqual } from './settings/FormControls'
import { useConfirm } from './ConfirmDialog'
import { resolveDefaultModel } from '../utils/model'

interface ModelOpt { model_id: string; name: string }
interface Voice { id: string; name: string }

interface Props {
  agent: TalkAgent
  defaultOpen?: boolean
  models: ModelOpt[]
  voices: Voice[]
  legacyTools: ChatToolInfo[]
  onSave: (patch: Partial<TalkAgent>) => Promise<void>
  onReset: () => Promise<void>
}

function snapshot(agent: TalkAgent) {
  return {
    voice_id: agent.voice_id,
    default_model: agent.default_model ?? '',
    tools: [...agent.enabled_tools],
  }
}

/** Settings card for one realtime voice agent. Deliberately styled apart from the
 *  text AgentCard (live-agent-card-* classes, mic accent) since voice agents have
 *  a leaner config surface: voice, model, tools — no params/thinking/skills/MCP. */
export default function LiveAgentCard({
  agent, defaultOpen = false, models, voices, legacyTools, onSave, onReset,
}: Props) {
  const confirm = useConfirm()
  const [open, setOpen] = useState(defaultOpen)
  const initial = useMemo(() => snapshot(agent), [agent])
  const [state, setState] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { setState(snapshot(agent)); setError(null) }, [agent])

  // Resolve the model to show the same way every module does (resolveDefaultModel):
  // the agent's own default, else the first eligible model — never an empty pick.
  const resolvedModel = useMemo(
    () => resolveDefaultModel(models, state.default_model || undefined),
    [models, state.default_model],
  )

  const dirty = useMemo(() => (
    state.voice_id !== initial.voice_id
    || state.default_model !== initial.default_model
    || !arrayEqual(state.tools, initial.tools)
  ), [state, initial])

  const toggle = (list: string[], name: string) => (
    list.includes(name) ? list.filter(x => x !== name) : [...list, name]
  )

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const patch: Partial<TalkAgent> = {}
      if (state.voice_id !== initial.voice_id) patch.voice_id = state.voice_id
      if (state.default_model !== initial.default_model) patch.default_model = state.default_model || null
      if (!arrayEqual(state.tools, initial.tools)) patch.enabled_tools = state.tools
      await onSave(patch)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!(await confirm({ title: 'Reset voice agent', message: `Reset "${agent.name}" to built-in defaults? This clears your overrides.`, confirmLabel: 'Reset', danger: true }))) return
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
    <div className="settings-module-card live-agent-card">
      <button
        type="button"
        className="settings-module-header live-agent-card-header"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className="live-agent-card-title">
          <span className="live-agent-card-avatar">{agent.avatar}</span>
          <span className="settings-module-name">{agent.name}</span>
        </span>
        <span className="live-agent-card-summary">
          {resolvedModel || '—'}
          <span className="live-agent-card-chevron" aria-hidden>{open ? '▾' : '▸'}</span>
        </span>
      </button>

      {open && (
        <div className="settings-module-body live-agent-card-body">
          <p className="live-agent-card-desc">{agent.description}</p>

          {/* Model — first field, consistent with the chat AgentCard. */}
          <div className="agent-field">
            <label className="panel-label">Model</label>
            <select
              className="select"
              style={{ width: '100%', maxWidth: 360 }}
              value={resolvedModel}
              onChange={(e) => setState(s => ({ ...s, default_model: e.target.value }))}
            >
              {models.map(m => <option key={m.model_id} value={m.model_id}>{m.name}</option>)}
            </select>
          </div>

          {/* Voice */}
          <div className="agent-field">
            <label className="panel-label">Voice</label>
            <select
              className="select"
              style={{ width: '100%', maxWidth: 360 }}
              value={state.voice_id}
              onChange={(e) => setState(s => ({ ...s, voice_id: e.target.value }))}
            >
              {voices.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>

          {/* Tools (legacy) — [] = pure conversation */}
          <ToggleGroup
            label="Tools"
            items={legacyTools}
            enabled={state.tools}
            onToggle={(n) => setState(s => ({ ...s, tools: toggle(s.tools, n) }))}
            emptyHint="No tools available."
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
