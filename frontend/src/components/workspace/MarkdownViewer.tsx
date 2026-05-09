import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { authFetch } from '../../api/client'

interface Props {
  url: string
}

export default function MarkdownViewer({ url }: Props) {
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setText(null)
    setError(null)
    authFetch(url)
      .then(r => r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(t => { if (!cancelled) setText(t) })
      .catch(e => { if (!cancelled) setError(e.message || 'Failed to load') })
    return () => { cancelled = true }
  }, [url])

  if (error) return <div className="workspace-viewer-error">⚠ {error}</div>
  if (text === null) return <div className="workspace-viewer-loading">Loading…</div>
  return (
    <div className="workspace-md aui-md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  )
}
