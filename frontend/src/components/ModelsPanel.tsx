import { useState, useEffect, useCallback } from 'react'
import { getModels, addModel, updateModel, deleteModel } from '../api/client'

const API_PROVIDERS = ['Bedrock', 'BedrockInvoke', 'Gemini', 'OpenAI']
const CATEGORIES = ['text', 'vision', 'image', 'video', 'reasoning', 'embedding']
const MODALITIES = ['text', 'document', 'image', 'video', 'audio']

interface ModelInfo {
  name: string; model_id: string; api_provider: string; vendor: string
  category: string; description: string
  capabilities: { input_modality: string[]; output_modality: string[]; streaming: boolean; tool_use: boolean; reasoning: boolean; context_window: number }
}

const emptyForm = (): ModelInfo => ({
  name: '', model_id: '', api_provider: 'Bedrock', vendor: '', category: 'text', description: '',
  capabilities: { input_modality: ['text'], output_modality: ['text'], streaming: true, tool_use: false, reasoning: false, context_window: 131072 },
})

export default function ModelsPanel() {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [editing, setEditing] = useState<ModelInfo | null>(null)
  const [isNew, setIsNew] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => setModels(await getModels()), [])
  useEffect(() => { load() }, [])

  const openAdd = () => { setEditing(emptyForm()); setIsNew(true) }
  const openEdit = (m: ModelInfo) => { setEditing({ ...m, capabilities: { ...m.capabilities } }); setIsNew(false) }

  const handleSave = async () => {
    if (!editing) return
    setSaving(true)
    const payload = {
      name: editing.name, model_id: editing.model_id, api_provider: editing.api_provider,
      vendor: editing.vendor, category: editing.category, description: editing.description,
      ...editing.capabilities,
    }
    if (isNew) await addModel(payload); else await updateModel(payload)
    setSaving(false); setEditing(null); load()
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this model?')) return
    await deleteModel(id); load()
  }

  const cap = editing?.capabilities
  const setCap = (k: string, v: unknown) => setEditing(e => e ? { ...e, capabilities: { ...e.capabilities, [k]: v } } : e)

  return (
    <div className="settings-panel">
      <div className="module-options-bar">
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>Model Management</span>
        <div className="text-options">
          <button className="text-btn text-btn--secondary" onClick={load} style={{ fontSize: 11, padding: '2px 10px' }}>🔄 Refresh</button>
          <button className="text-btn text-btn--primary" onClick={openAdd} style={{ fontSize: 11, padding: '2px 10px' }}>➕ Add Model</button>
        </div>
      </div>

      <div className="settings-content">
        <table className="settings-table">
          <thead>
            <tr><th>Name</th><th>Model ID</th><th>Provider</th><th>Category</th><th>Streaming</th><th>Tool Use</th><th>Reasoning</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.model_id}>
                <td>{m.name}</td>
                <td className="settings-session-id">{m.model_id}</td>
                <td>{m.api_provider}</td>
                <td>{m.category}</td>
                <td>{m.capabilities.streaming ? '✓' : ''}</td>
                <td>{m.capabilities.tool_use ? '✓' : ''}</td>
                <td>{m.capabilities.reasoning ? '✓' : ''}</td>
                <td>
                  <button className="settings-action-btn" onClick={() => openEdit(m)} title="Edit">✏️</button>
                  <button className="settings-action-btn settings-action-btn--danger" onClick={() => handleDelete(m.model_id)} title="Delete">🗑️</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {editing && (
          <div className="settings-modal-overlay" onClick={() => setEditing(null)}>
            <div className="settings-modal" onClick={e => e.stopPropagation()}>
              <h3 style={{ margin: '0 0 16px' }}>{isNew ? 'Add Model' : 'Edit Model'}</h3>

              <label className="text-panel-label">Model ID</label>
              <input className="draw-seed-input" style={{ width: '100%', marginBottom: 8 }} value={editing.model_id}
                onChange={e => setEditing({ ...editing, model_id: e.target.value })} disabled={!isNew} />

              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <label className="text-panel-label">Name</label>
                  <input className="draw-seed-input" style={{ width: '100%' }} value={editing.name}
                    onChange={e => setEditing({ ...editing, name: e.target.value })} />
                </div>
                <div style={{ flex: 1 }}>
                  <label className="text-panel-label">Vendor</label>
                  <input className="draw-seed-input" style={{ width: '100%' }} value={editing.vendor}
                    onChange={e => setEditing({ ...editing, vendor: e.target.value })} />
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <div style={{ flex: 1 }}>
                  <label className="text-panel-label">API Provider</label>
                  <select className="top-bar-select" style={{ width: '100%' }} value={editing.api_provider}
                    onChange={e => setEditing({ ...editing, api_provider: e.target.value })}>
                    {API_PROVIDERS.map(p => <option key={p}>{p}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label className="text-panel-label">Category</label>
                  <select className="top-bar-select" style={{ width: '100%' }} value={editing.category}
                    onChange={e => setEditing({ ...editing, category: e.target.value })}>
                    {CATEGORIES.map(c => <option key={c}>{c}</option>)}
                  </select>
                </div>
              </div>

              <label className="text-panel-label" style={{ marginTop: 8 }}>Context Window</label>
              <input className="draw-seed-input" type="number" style={{ width: 160 }} value={cap?.context_window ?? 0}
                onChange={e => setCap('context_window', Number(e.target.value))} />

              <label className="text-panel-label" style={{ marginTop: 8 }}>Input Modalities</label>
              <div className="settings-tools-grid">
                {MODALITIES.map(m => (
                  <label key={m} className="draw-checkbox-label">
                    <input type="checkbox" checked={cap?.input_modality.includes(m)}
                      onChange={e => setCap('input_modality', e.target.checked ? [...(cap?.input_modality || []), m] : cap?.input_modality.filter((x: string) => x !== m))} />
                    {m}
                  </label>
                ))}
              </div>

              <label className="text-panel-label">Output Modalities</label>
              <div className="settings-tools-grid">
                {MODALITIES.map(m => (
                  <label key={m} className="draw-checkbox-label">
                    <input type="checkbox" checked={cap?.output_modality.includes(m)}
                      onChange={e => setCap('output_modality', e.target.checked ? [...(cap?.output_modality || []), m] : cap?.output_modality.filter((x: string) => x !== m))} />
                    {m}
                  </label>
                ))}
              </div>

              <label className="text-panel-label">Capabilities</label>
              <div className="settings-tools-grid">
                <label className="draw-checkbox-label"><input type="checkbox" checked={cap?.streaming} onChange={e => setCap('streaming', e.target.checked)} /> Streaming</label>
                <label className="draw-checkbox-label"><input type="checkbox" checked={cap?.tool_use} onChange={e => setCap('tool_use', e.target.checked)} /> Tool Use</label>
                <label className="draw-checkbox-label"><input type="checkbox" checked={cap?.reasoning} onChange={e => setCap('reasoning', e.target.checked)} /> Reasoning</label>
              </div>

              <div className="settings-modal-actions">
                <button className="text-btn text-btn--secondary" onClick={() => setEditing(null)}>Cancel</button>
                <button className="text-btn text-btn--primary" onClick={handleSave} disabled={saving}>
                  {saving ? '⏳ Saving...' : '💾 Save'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
