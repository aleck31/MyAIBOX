import { useState, useEffect, useCallback } from 'react'
import { getMcpServers, addMcpServer, deleteMcpServer, toggleMcpServer } from '../api/client'

interface McpServer { name: string; type: string; status: string; url: string; tools_count: number }

export default function McpPanel() {
  const [servers, setServers] = useState<McpServer[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', type: 'http', url: '', args: '' })

  const load = useCallback(async () => setServers(await getMcpServers()), [])
  useEffect(() => { load() }, [])

  const handleAdd = async () => {
    if (!form.name.trim()) return
    await addMcpServer(form)
    setForm({ name: '', type: 'http', url: '', args: '' })
    setShowAdd(false); load()
  }

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete MCP server "${name}"?`)) return
    await deleteMcpServer(name); load()
  }

  const handleToggle = async (name: string, currentStatus: string) => {
    await toggleMcpServer(name, currentStatus === 'Enabled')
    load()
  }

  return (
    <div className="settings-panel">
      <div className="module-options-bar">
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>MCP Server Management</span>
        <div className="text-options">
          <button className="text-btn text-btn--secondary" onClick={load} style={{ fontSize: 11, padding: '2px 10px' }}>🔄 Refresh</button>
          <button className="text-btn text-btn--primary" onClick={() => setShowAdd(true)} style={{ fontSize: 11, padding: '2px 10px' }}>➕ Add Server</button>
        </div>
      </div>

      <div className="settings-content">
        <table className="settings-table">
          <thead>
            <tr><th>Name</th><th>Type</th><th>Status</th><th>Tools</th><th>URL / Command</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {servers.map((s) => (
              <tr key={s.name}>
                <td>{s.name}</td>
                <td>{s.type}</td>
                <td>{s.status}</td>
                <td>{s.tools_count}</td>
                <td className="settings-session-id" style={{ maxWidth: 300 }}>{s.url}</td>
                <td>
                  <button className="settings-action-btn" onClick={() => handleToggle(s.name, s.status)} title={s.status === 'Enabled' ? 'Disable' : 'Enable'}>
                    {s.status === 'Enabled' ? '❌' : '✅'}
                  </button>
                  <button className="settings-action-btn settings-action-btn--danger" onClick={() => handleDelete(s.name)} title="Delete">🗑️</button>
                </td>
              </tr>
            ))}
            {servers.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'hsl(var(--muted-foreground))' }}>No MCP servers configured</td></tr>
            )}
          </tbody>
        </table>

        {showAdd && (
          <div className="settings-modal-overlay" onClick={() => setShowAdd(false)}>
            <div className="settings-modal" onClick={e => e.stopPropagation()}>
              <h3 style={{ margin: '0 0 16px' }}>Add MCP Server</h3>

              <label className="text-panel-label">Server Name</label>
              <input className="draw-seed-input" style={{ width: '100%', marginBottom: 8 }} value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })} placeholder="my-server" />

              <label className="text-panel-label">Type</label>
              <select className="top-bar-select" style={{ width: '100%', marginBottom: 8 }} value={form.type}
                onChange={e => setForm({ ...form, type: e.target.value })}>
                <option value="http">HTTP</option>
                <option value="stdio">stdio</option>
                <option value="sse">SSE</option>
              </select>

              <label className="text-panel-label">{form.type === 'stdio' ? 'Command' : 'URL'}</label>
              <input className="draw-seed-input" style={{ width: '100%', marginBottom: 8 }} value={form.url}
                onChange={e => setForm({ ...form, url: e.target.value })}
                placeholder={form.type === 'stdio' ? 'uvx' : 'https://api.example.com/mcp'} />

              {form.type === 'stdio' && (
                <>
                  <label className="text-panel-label">Arguments (JSON array)</label>
                  <input className="draw-seed-input" style={{ width: '100%', marginBottom: 8 }} value={form.args}
                    onChange={e => setForm({ ...form, args: e.target.value })} placeholder='["arg1", "arg2"]' />
                </>
              )}

              <div className="settings-modal-actions">
                <button className="text-btn text-btn--secondary" onClick={() => setShowAdd(false)}>Cancel</button>
                <button className="text-btn text-btn--primary" onClick={handleAdd}>➕ Add</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
