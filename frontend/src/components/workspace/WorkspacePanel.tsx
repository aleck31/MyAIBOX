import { useCallback, useEffect, useImperativeHandle, useState, forwardRef } from 'react'
import {
  listChatWorkspace,
  deleteChatWorkspaceFile,
  type WorkspaceFile,
} from '../../api/client'
import WorkspaceFileList from './WorkspaceFileList'
import WorkspaceFileViewer from './WorkspaceFileViewer'
import { IconRefresh, IconClose } from '../icons'

export interface WorkspacePanelHandle {
  refresh: () => void
}

interface Props {
  agentId: string
  onClose?: () => void
}

function WorkspacePanel({ agentId, onClose }: Props, ref: React.Ref<WorkspacePanelHandle>) {
  const [files, setFiles] = useState<WorkspaceFile[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const res = await listChatWorkspace(agentId)
      setFiles(res.files || [])
      setSelected(prev => {
        if (prev && res.files?.some(f => f.name === prev)) return prev
        return res.files?.[0]?.name ?? null
      })
    } catch (err) {
      console.error('Workspace load failed:', err)
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useImperativeHandle(ref, () => ({ refresh }), [refresh])

  useEffect(() => { refresh() }, [refresh])

  const handleDelete = useCallback(async (name: string) => {
    if (!confirm(`Delete "${name}"?`)) return
    try {
      await deleteChatWorkspaceFile(agentId, name)
      await refresh()
    } catch (err) {
      console.error('Delete failed:', err)
    }
  }, [agentId, refresh])

  return (
    <div className="workspace-panel">
      <div className="workspace-header">
        <span className="workspace-title">
          Workspace File <span className="workspace-count">({files.length})</span>
        </span>
        <div className="workspace-actions">
          <button className="bar-icon-btn" onClick={refresh} disabled={loading} title="Refresh">
            <IconRefresh size={14} className={loading ? 'spin' : ''} />
          </button>
          {onClose && (
            <button className="bar-icon-btn" onClick={onClose} title="Close">
              <IconClose size={14} />
            </button>
          )}
        </div>
      </div>

      <div className="workspace-file-list-container">
        <WorkspaceFileList
          files={files}
          selected={selected}
          onSelect={setSelected}
          onDelete={handleDelete}
        />
      </div>

      <div className="workspace-viewer-container">
        {selected ? (
          <>
            <button
              className="workspace-viewer-close"
              onClick={() => setSelected(null)}
              title={`Close ${selected}`}
            ><IconClose size={12} /></button>
            <WorkspaceFileViewer key={selected} agentId={agentId} name={selected} />
          </>
        ) : (
          <div className="workspace-viewer-empty">Select a file to preview</div>
        )}
      </div>
    </div>
  )
}

export default forwardRef(WorkspacePanel)
