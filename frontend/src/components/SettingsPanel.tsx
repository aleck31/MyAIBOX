import { useState, useEffect, useCallback } from 'react'
import { getSettingsSessions, deleteSession, clearSessionHistory } from '../api/client'
import { Button } from './Button'
import { IconRefresh, IconTrash, IconEraser } from './icons'
import type { SessionInfo } from '../types/settings'

export default function SettingsPanel({ username }: { username: string }) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])

  const loadSessions = useCallback(async () => {
    setSessions(await getSettingsSessions())
  }, [])

  useEffect(() => { loadSessions() }, [loadSessions])

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

  return (
    <div className="settings-panel">
      <div className="section-bar">
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>Active Sessions for {username}</span>
        <div className="section-actions">
          <Button onClick={loadSessions}><IconRefresh size={14} style={{ marginRight: 4 }} />Refresh</Button>
        </div>
      </div>
      <div className="settings-content">
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
                    <Button variant="ghost" onClick={() => handleClearHistory(s.session_id)} title="Clear history" style={{ padding: '2px 4px', minHeight: 0 }}><IconEraser size={14} /></Button>
                    <Button variant="danger" onClick={() => handleDelete(s.session_id)} title="Delete" style={{ padding: '2px 4px', minHeight: 0, border: 'none' }}><IconTrash size={14} /></Button>
                  </td>
                </tr>
              ))}
              {sessions.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'hsl(var(--muted-foreground))' }}>No active sessions</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
