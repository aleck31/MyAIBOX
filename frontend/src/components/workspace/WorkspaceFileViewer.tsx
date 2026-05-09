import MarkdownViewer from './MarkdownViewer'
import ImageViewer from './ImageViewer'
import PdfViewer from './PdfViewer'
import { assistantWorkspaceFileUrl } from '../../api/client'

interface Props {
  name: string
}

function extensionOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i < 0 ? '' : name.slice(i + 1).toLowerCase()
}

export default function WorkspaceFileViewer({ name }: Props) {
  const url = assistantWorkspaceFileUrl(name)
  const ext = extensionOf(name)

  if (ext === 'md' || ext === 'markdown') return <MarkdownViewer url={url} />
  if (ext === 'pdf') return <PdfViewer url={url} name={name} />
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) {
    return <ImageViewer url={url} name={name} />
  }

  // Fallback: show a download link for unsupported types.
  return (
    <div className="workspace-viewer-fallback">
      <p>Preview not available for <code>.{ext || 'unknown'}</code></p>
      <a href={url} download={name} className="btn">⬇ Download {name}</a>
    </div>
  )
}
