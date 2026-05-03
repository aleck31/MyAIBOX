import { useState, useEffect, useCallback } from 'react'
import { getSettingsSessions, deleteSession, clearSessionHistory, getModulesConfig, updateModuleConfig } from '../api/client'
import { Button } from './Button'
import { Modal, ModalActions } from './Modal'
import type { SessionInfo, ModulesData, ModuleConfig } from '../types/settings'

export default function SettingsPanel({ username, tab = 'account' }: { username: string; tab?: 'account' | 'modules' }) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [modulesData, setModulesData] = useState<ModulesData | null>(null)
  const [editingModule, setEditingModule] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<ModuleConfig | null>(null)
  const [saving, setSaving] = useState(false)

  const loadSessions = useCallback(async () => {
    setSessions(await getSettingsSessions())
  }, [])

  const loadModules = useCallback(async () => {
    setModulesData(await getModulesConfig())
  }, [])

  useEffect(() => {
    loadSessions()
    loadModules()
  }, [])

  const handleDelete = useCallback(async (id: string) => {
    if (!confirm('Delete this session?')) return
    await deleteSession(id)
    loadSessions()
  }, [loadSessions])

  const handleClearHistory = useCallback(async (id: string) => {
    if (!confirm('Clear history for this session?')) return
    await clearSessionHistory(id)
    loadSessions()
  }, [loadSessions])

  const handleEdit = useCallback((name: string) => {
    if (!modulesData) return
    setEditingModule(name)
    setEditForm({ ...modulesData.modules[name] })
  }, [modulesData])

  const handleSave = useCallback(async () => {
    if (!editingModule || !editForm) return
    setSaving(true)
    await updateModuleConfig(editingModule, editForm)
    setSaving(false)
    setEditingModule(null)
    loadModules()
  }, [editingModule, editForm, loadModules])

  return (
    <div className="settings-panel">
      {tab === 'account' && (
        <div className="section-bar">
          <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>Active Sessions for {username}</span>
          <div className="section-actions">
            <Button onClick={loadSessions}>🔃 Refresh</Button>
          </div>
        </div>
      )}
      {tab === 'modules' && (
        <div className="section-bar">
          <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>Module Configuration</span>
        </div>
      )}
      <div className="settings-content">
        {tab === 'account' && (
          <div className="settings-section">
            <table className="settings-table">
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Session ID</th>
                  <th>Records</th>
                  <th>Created</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.session_id}>
                    <td>{s.module}</td>
                    <td className="settings-session-id">{s.session_id}</td>
                    <td>{s.records}</td>
                    <td>{new Date(s.created).toLocaleString()}</td>
                    <td>{new Date(s.updated).toLocaleString()}</td>
                    <td>
                      <Button variant="ghost" onClick={() => handleClearHistory(s.session_id)} title="Clear history" style={{ padding: '2px 4px', minHeight: 0 }}>🧹</Button>
                      <Button variant="danger" onClick={() => handleDelete(s.session_id)} title="Delete" style={{ padding: '2px 4px', minHeight: 0, border: 'none' }}>🗑️</Button>
                    </td>
                  </tr>
                ))}
                {sessions.length === 0 && (
                  <tr><td colSpan={6} style={{ textAlign: 'center', color: 'hsl(var(--muted-foreground))' }}>No active sessions</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {tab === 'modules' && modulesData && (
          <div className="settings-section">
            {Object.entries(modulesData.modules).map(([name, cfg]) => (
              <div key={name} className="settings-module-card">
                <div className="settings-module-header">
                  <span className="settings-module-name">{name}</span>
                  <Button onClick={() => handleEdit(name)}>✏️ Edit</Button>
                </div>
                <div className="settings-module-body">
                  <div className="settings-field">
                    <span className="settings-field-label">Model:</span>
                    <span className="settings-field-value">{cfg.default_model || '—'}</span>
                  </div>
                  {cfg.enabled_tools.length > 0 && (
                    <div className="settings-field">
                      <span className="settings-field-label">Tools:</span>
                      <span className="settings-field-value">{cfg.enabled_tools.join(', ')}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Edit modal */}
            {editingModule && editForm && (
              <Modal open onClose={() => setEditingModule(null)}>
                <h3 style={{ margin: '0 0 16px' }}>{editingModule} Module Settings</h3>

                <label className="panel-label">Default Model</label>
                <select
                  className="select"
                  value={editForm.default_model}
                  onChange={(e) => setEditForm({ ...editForm, default_model: e.target.value })}
                  style={{ width: '100%', marginBottom: 12 }}
                >
                  <option value="">— None —</option>
                  {modulesData.model_choices.map((m) => (
                    <option key={m.model_id} value={m.model_id}>{m.name}</option>
                  ))}
                </select>

                <label className="panel-label">Parameters (JSON)</label>
                <textarea
                  className="panel-textarea"
                  value={editForm.parameters}
                  onChange={(e) => setEditForm({ ...editForm, parameters: e.target.value })}
                  rows={6}
                  style={{ fontFamily: 'monospace', fontSize: 12, marginBottom: 12 }}
                />

                <label className="panel-label">Enabled Tools</label>
                <div className="settings-tools-grid">
                  {modulesData.available_tools.map((t) => (
                    <label key={t} className="draw-checkbox-label">
                      <input
                        type="checkbox"
                        checked={editForm.enabled_tools.includes(t)}
                        onChange={(e) => {
                          const tools = e.target.checked
                            ? [...editForm.enabled_tools, t]
                            : editForm.enabled_tools.filter((x) => x !== t)
                          setEditForm({ ...editForm, enabled_tools: tools })
                        }}
                      />
                      {t}
                    </label>
                  ))}
                </div>

                <ModalActions>
                  <Button onClick={() => setEditingModule(null)}>Cancel</Button>
                  <Button variant="primary" onClick={handleSave} disabled={saving}>
                    {saving ? '⏳ Saving...' : '💾 Save'}
                  </Button>
                </ModalActions>
              </Modal>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
