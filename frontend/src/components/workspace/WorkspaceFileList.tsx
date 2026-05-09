import type { WorkspaceFile } from '../../api/client'

interface Props {
  files: WorkspaceFile[]
  selected: string | null
  onSelect: (name: string) => void
  onDelete: (name: string) => void
}

const EXT_ICON: Record<string, string> = {
  md: '📄', markdown: '📄', txt: '📄',
  pdf: '📑',
  png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️', webp: '🖼️', svg: '🖼️',
  json: '⚙️', csv: '📊', xlsx: '📊',
}

function iconFor(name: string): string {
  const i = name.lastIndexOf('.')
  const ext = i < 0 ? '' : name.slice(i + 1).toLowerCase()
  return EXT_ICON[ext] || '📎'
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** Relative time: "just now" / "5m" / "2h" / "3d"; fall back to date for older. */
function formatMtime(unixSeconds: number): string {
  const diffSec = Date.now() / 1000 - unixSeconds
  if (diffSec < 45) return 'just now'
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`
  if (diffSec < 86400 * 7) return `${Math.round(diffSec / 86400)}d ago`
  return new Date(unixSeconds * 1000).toLocaleDateString()
}

export default function WorkspaceFileList({ files, selected, onSelect, onDelete }: Props) {
  if (files.length === 0) {
    return <div className="workspace-empty">No files yet. Ask the agent to save a report.</div>
  }
  return (
    <ul className="workspace-file-list">
      {files.map(f => (
        <li
          key={f.name}
          className={`workspace-file${f.name === selected ? ' is-selected' : ''}`}
          onClick={() => onSelect(f.name)}
        >
          <span className="workspace-file-icon">{iconFor(f.name)}</span>
          <span className="workspace-file-name" title={f.name}>{f.name}</span>
          <span className="workspace-file-size">{formatSize(f.size)}</span>
          <span className="workspace-file-mtime" title={new Date(f.mtime * 1000).toLocaleString()}>
            {formatMtime(f.mtime)}
          </span>
          <button
            className="workspace-file-delete"
            title="Delete"
            onClick={(e) => { e.stopPropagation(); onDelete(f.name) }}
          >🗑</button>
        </li>
      ))}
    </ul>
  )
}
