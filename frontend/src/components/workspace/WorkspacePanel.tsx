import { useCallback, useEffect, useImperativeHandle, useState, forwardRef } from 'react'
import {
  listAssistantWorkspace,
  deleteAssistantWorkspaceFile,
  type WorkspaceFile,
} from '../../api/client'
import WorkspaceFileList from './WorkspaceFileList'
import WorkspaceFileViewer from './WorkspaceFileViewer'

export interface WorkspacePanelHandle {
  refresh: () => void
}

interface Props {
  onClose?: () => void
}

function WorkspacePanel({ onClose }: Props, ref: React.Ref<WorkspacePanelHandle>) {
  const [files, setFiles] = useState<WorkspaceFile[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const res = await listAssistantWorkspace()
      setFiles(res.files || [])
      // Keep current selection if still present; otherwise fall back to first.
      setSelected(prev => {
        if (prev && res.files?.some(f => f.name === prev)) return prev
        return res.files?.[0]?.name ?? null
      })
    } catch (err) {
      console.error('Workspace load failed:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useImperativeHandle(ref, () => ({ refresh }), [refresh])

  useEffect(() => { refresh() }, [refresh])

  const handleDelete = useCallback(async (name: string) => {
    if (!confirm(`Delete "${name}"?`)) return
    try {
      await deleteAssistantWorkspaceFile(name)
      await refresh()
    } catch (err) {
      console.error('Delete failed:', err)
    }
  }, [refresh])

  return (
    <div className="workspace-panel">
      <div className="workspace-header">
        <span className="workspace-title">📁 Workspace <span className="workspace-count">({files.length})</span></span>
        <div className="workspace-actions">
          <button className="bar-icon-btn" onClick={refresh} disabled={loading} title="Refresh">
            <span className={loading ? 'spin' : ''} style={{ display: 'inline-block' }}>🔄</span>
          </button>
          {onClose && (
            <button className="bar-icon-btn" onClick={onClose} title="Close">✕</button>
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
            >✕</button>
            <WorkspaceFileViewer key={selected} name={selected} />
          </>
        ) : (
          <div className="workspace-viewer-empty">Select a file to preview</div>
        )}
      </div>
    </div>
  )
}

export default forwardRef(WorkspacePanel)
