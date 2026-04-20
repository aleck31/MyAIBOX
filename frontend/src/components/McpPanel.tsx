import { useState, useEffect, useCallback } from 'react'
import { getMcpServers, addMcpServer, deleteMcpServer, toggleMcpServer } from '../api/client'
import { Button } from './Button'
import { Modal, ModalActions } from './Modal'

const ACTION_BTN_STYLE = { padding: '2px 4px', minHeight: 0 } as const

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
        <div className="module-options">
          <Button onClick={load} style={{ fontSize: 11, padding: '2px 10px' }}>🔄 Refresh</Button>
          <Button variant="primary" onClick={() => setShowAdd(true)} style={{ fontSize: 11, padding: '2px 10px' }}>➕ Add Server</Button>
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
                  <Button variant="ghost" onClick={() => handleToggle(s.name, s.status)} title={s.status === 'Enabled' ? 'Disable' : 'Enable'} style={ACTION_BTN_STYLE}>
                    {s.status === 'Enabled' ? '❌' : '✅'}
                  </Button>
                  <Button variant="danger" onClick={() => handleDelete(s.name)} title="Delete" style={{ ...ACTION_BTN_STYLE, border: 'none' }}>🗑️</Button>
                </td>
              </tr>
            ))}
            {servers.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'hsl(var(--muted-foreground))' }}>No MCP servers configured</td></tr>
            )}
          </tbody>
        </table>

        {showAdd && (
          <Modal open onClose={() => setShowAdd(false)}>
            <h3 style={{ margin: '0 0 16px' }}>Add MCP Server</h3>

            <label className="panel-label">Server Name</label>
            <input className="input" style={{ width: '100%', marginBottom: 8 }} value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })} placeholder="my-server" />

            <label className="panel-label">Type</label>
            <select className="select" style={{ width: '100%', marginBottom: 8 }} value={form.type}
              onChange={e => setForm({ ...form, type: e.target.value })}>
              <option value="http">HTTP</option>
              <option value="stdio">stdio</option>
              <option value="sse">SSE</option>
            </select>

            <label className="panel-label">{form.type === 'stdio' ? 'Command' : 'URL'}</label>
            <input className="input" style={{ width: '100%', marginBottom: 8 }} value={form.url}
              onChange={e => setForm({ ...form, url: e.target.value })}
              placeholder={form.type === 'stdio' ? 'uvx' : 'https://api.example.com/mcp'} />

            {form.type === 'stdio' && (
              <>
                <label className="panel-label">Arguments (JSON array)</label>
                <input className="input" style={{ width: '100%', marginBottom: 8 }} value={form.args}
                  onChange={e => setForm({ ...form, args: e.target.value })} placeholder='["arg1", "arg2"]' />
              </>
            )}

            <ModalActions>
              <Button onClick={() => setShowAdd(false)}>Cancel</Button>
              <Button variant="primary" onClick={handleAdd}>➕ Add</Button>
            </ModalActions>
          </Modal>
        )}
      </div>
    </div>
  )
}
