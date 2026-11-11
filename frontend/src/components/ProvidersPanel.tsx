import { useState, useEffect, useCallback } from 'react'
import { getProviders, saveProvider, deleteProvider } from '../api/client'
import { API_LABELS, BEDROCK_APIS, apiLabel, type ProviderInfo } from '../utils/llmApi'
import { Button } from './Button'
import { Modal, ModalActions } from './Modal'
import { useConfirm } from './ConfirmDialog'
import { IconRefresh, IconEdit, IconTrash, IconPlus } from './icons'
import SectionBar from './SectionBar'

interface ProviderForm {
  name: string; auth: 'aws' | 'api_key'; apis: string[]; base_url: string; region: string
  keySource: 'secret' | 'inline'; secret_name: string; api_key: string; has_api_key: boolean
}

const emptyForm = (): ProviderForm => ({
  name: '', auth: 'api_key', apis: [], base_url: '', region: '',
  keySource: 'secret', secret_name: '', api_key: '', has_api_key: false,
})

const toForm = (p: ProviderInfo): ProviderForm => ({
  name: p.name, auth: p.auth, apis: [...p.apis], base_url: p.base_url, region: p.region,
  keySource: p.has_api_key ? 'inline' : 'secret', secret_name: p.secret_name, api_key: '', has_api_key: p.has_api_key,
})

// AWS credentials sign Bedrock calls only; the bidirectional stream (Nova Sonic) cannot take a Bearer key.
const apisFor = (auth: ProviderForm['auth']) =>
  Object.keys(API_LABELS).filter(a => auth === 'aws' ? BEDROCK_APIS.includes(a) : a !== 'bedrock-bidi-stream')

export default function ProvidersPanel() {
  const confirm = useConfirm()
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [canEdit, setCanEdit] = useState(false)
  const [editing, setEditing] = useState<ProviderForm | null>(null)
  const [isNew, setIsNew] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async (refresh = false) => {
    const data = await getProviders({ refresh })
    setProviders(data.providers ?? [])
    setCanEdit(!!data.can_edit)
  }, [])
  useEffect(() => { load() }, [load])

  const setAuth = (auth: ProviderForm['auth']) =>
    setEditing(e => e ? { ...e, auth, apis: e.apis.filter(a => apisFor(auth).includes(a)) } : e)
  const toggleApi = (api: string, on: boolean) =>
    setEditing(e => e ? { ...e, apis: on ? [...e.apis, api] : e.apis.filter(a => a !== api) } : e)

  const handleSave = async () => {
    if (!editing) return
    const keyed = editing.auth === 'api_key'
    const payload: Record<string, unknown> = {
      name: editing.name, auth: editing.auth, apis: editing.apis, base_url: editing.base_url, region: editing.region,
      secret_name: keyed && editing.keySource === 'secret' ? editing.secret_name : '',
    }
    // Leaving the key field empty keeps the stored key; switching to a secret or to AWS clears it.
    if (!keyed || editing.keySource === 'secret') payload.api_key = ''
    else if (editing.api_key) payload.api_key = editing.api_key
    setSaving(true)
    const res = await saveProvider(payload, isNew)
    setSaving(false)
    if (res?.ok === false) { window.alert(res.error || 'Failed to save provider'); return }
    setEditing(null); load()
  }

  const handleDelete = async (name: string) => {
    if (!(await confirm({ title: 'Delete provider', message: `Delete provider "${name}"?`, confirmLabel: 'Delete', danger: true }))) return
    const res = await deleteProvider(name)
    if (res?.ok === false) window.alert(res.error || 'Failed to delete provider')
    load()
  }

  return (
    <div className="settings-panel">
      <SectionBar>
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>
          LLM Providers{canEdit ? '' : ' (read-only: admins only)'}
        </span>
        <div className="section-actions">
          <Button onClick={() => load(true)}><IconRefresh size={14} style={{ marginRight: 4 }} />Refresh</Button>
          {canEdit && (
            <Button variant="primary" onClick={() => { setEditing(emptyForm()); setIsNew(true) }}>
              <IconPlus size={14} style={{ marginRight: 4 }} />Add Provider
            </Button>
          )}
        </div>
      </SectionBar>

      <div className="settings-content">
        <table className="settings-table">
          <thead>
            <tr><th>Name</th><th>Base URL</th><th>Auth</th><th>Region</th><th>APIs</th><th>Models</th>{canEdit && <th>Actions</th>}</tr>
          </thead>
          <tbody>
            {providers.map(p => (
              <tr key={p.name}>
                <td style={{ whiteSpace: 'nowrap' }}>{p.name}</td>
                <td className="settings-session-id">{p.base_url || 'official endpoint'}</td>
                <td>{p.auth === 'aws' ? 'AWS credentials' : p.secret_name ? `secret ${p.secret_name}` : 'API key'}</td>
                <td style={{ whiteSpace: 'nowrap' }}>{p.region}</td>
                <td>{p.apis.map(apiLabel).join(', ')}</td>
                <td>{p.models.length}</td>
                {canEdit && (
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <Button variant="ghost" onClick={() => { setEditing(toForm(p)); setIsNew(false) }} title="Edit" className="btn--row-action"><IconEdit size={16} /></Button>
                    <Button variant="danger" onClick={() => handleDelete(p.name)} title="Delete" className="btn--row-action" style={{ border: 'none' }}><IconTrash size={16} /></Button>
                  </td>
                )}
              </tr>
            ))}
            {providers.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: 'hsl(var(--muted-foreground))' }}>No providers configured</td></tr>
            )}
          </tbody>
        </table>

        {editing && (
          <Modal open onClose={() => setEditing(null)}>
            <h3 style={{ margin: '0 0 16px' }}>{isNew ? 'Add Provider' : 'Edit Provider'}</h3>

            <label className="panel-label">Name</label>
            <input className="input" style={{ width: '100%', marginBottom: 8 }} value={editing.name} disabled={!isNew}
              onChange={e => setEditing({ ...editing, name: e.target.value })} placeholder="agw" />

            <label className="panel-label">API Base URL</label>
            <input className="input" style={{ width: '100%', marginBottom: 8 }} value={editing.base_url}
              onChange={e => setEditing({ ...editing, base_url: e.target.value })}
              placeholder="Empty = the official endpoint of each API, e.g. https://agw.example.com" />

            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <label className="panel-label">Auth</label>
                <select className="select" style={{ width: '100%' }} value={editing.auth}
                  onChange={e => setAuth(e.target.value as ProviderForm['auth'])}>
                  <option value="api_key">API key</option>
                  <option value="aws">AWS credentials (SigV4)</option>
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <label className="panel-label">Region{editing.auth === 'aws' ? '' : ' (Bedrock APIs)'}</label>
                <input className="input" style={{ width: '100%' }} value={editing.region}
                  onChange={e => setEditing({ ...editing, region: e.target.value })} placeholder="us-west-2" />
              </div>
            </div>

            {editing.auth === 'api_key' && (
              <>
                <label className="panel-label" style={{ marginTop: 8 }}>API Key</label>
                <div className="settings-tools-grid">
                  <label className="draw-checkbox-label">
                    <input type="radio" checked={editing.keySource === 'secret'}
                      onChange={() => setEditing({ ...editing, keySource: 'secret' })} /> Secrets Manager secret
                  </label>
                  <label className="draw-checkbox-label">
                    <input type="radio" checked={editing.keySource === 'inline'}
                      onChange={() => setEditing({ ...editing, keySource: 'inline' })} /> Key
                  </label>
                </div>
                {editing.keySource === 'secret' ? (
                  <input className="input" style={{ width: '100%' }} value={editing.secret_name}
                    onChange={e => setEditing({ ...editing, secret_name: e.target.value })}
                    placeholder='Secret name; value {"api_key": "..."} or the bare key' />
                ) : (
                  <input className="input" type="password" autoComplete="off" style={{ width: '100%' }} value={editing.api_key}
                    onChange={e => setEditing({ ...editing, api_key: e.target.value })}
                    placeholder={editing.has_api_key ? 'Stored; leave empty to keep it' : 'API key'} />
                )}
              </>
            )}

            <label className="panel-label" style={{ marginTop: 8 }}>APIs</label>
            <div className="settings-tools-grid">
              {apisFor(editing.auth).map(api => (
                <label key={api} className="draw-checkbox-label">
                  <input type="checkbox" checked={editing.apis.includes(api)} onChange={e => toggleApi(api, e.target.checked)} />
                  {API_LABELS[api]}
                </label>
              ))}
            </div>

            <ModalActions>
              <Button onClick={() => setEditing(null)}>Cancel</Button>
              <Button variant="primary" onClick={handleSave} disabled={saving}>{saving ? '⏳ Saving...' : '💾 Save'}</Button>
            </ModalActions>
          </Modal>
        )}
      </div>
    </div>
  )
}
