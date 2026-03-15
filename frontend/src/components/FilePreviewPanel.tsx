import { useState, useEffect, useRef, useCallback } from 'react'
import ResizablePreview from './ResizablePreview'

interface Props {
  accept?: string
  label?: string
  placeholder?: string
  externalUrl?: string | null
  minHeight?: number
  onFileChange?: (file: File | null) => void
  onClear?: () => void
  className?: string
}

export default function FilePreviewPanel({
  accept = 'image/*',
  label = 'Source Image',
  placeholder = 'No file selected',
  externalUrl,
  minHeight = 150,
  onFileChange,
  onClear,
  className,
}: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const fileRef = useRef<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (blobUrl) URL.revokeObjectURL(blobUrl)
    setBlobUrl(null)
    fileRef.current = null
  }, [externalUrl])  // eslint-disable-line react-hooks/exhaustive-deps

  const previewUrl = blobUrl ?? externalUrl ?? null
  const isPdf = fileRef.current?.type === 'application/pdf'

  const setFile = useCallback((f: File | null) => {
    if (blobUrl) URL.revokeObjectURL(blobUrl)
    fileRef.current = f
    setBlobUrl(f ? URL.createObjectURL(f) : null)
    onFileChange?.(f)
  }, [blobUrl, onFileChange])

  const handleSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null
    if (f) setFile(f)
    if (e.target) e.target.value = ''
  }, [setFile])

  const handlePaste = useCallback(async () => {
    try {
      const items = await navigator.clipboard.read()
      for (const item of items) {
        const imageType = item.types.find(t => t.startsWith('image/'))
        if (imageType) {
          const blob = await item.getType(imageType)
          const ext = imageType.split('/')[1] || 'png'
          setFile(new File([blob], `paste.${ext}`, { type: imageType }))
          return
        }
      }
    } catch { /* clipboard not available */ }
  }, [setFile])

  const handleClear = useCallback(() => {
    if (blobUrl) URL.revokeObjectURL(blobUrl)
    setBlobUrl(null)
    fileRef.current = null
    onFileChange?.(null)
    onClear?.()
  }, [blobUrl, onFileChange, onClear])

  return (
    <div className={className}>
      <label className="text-panel-label">{label}</label>
      {previewUrl ? (
        <ResizablePreview minHeight={minHeight}>
          {isPdf ? (
            <iframe src={previewUrl} className="file-preview-iframe" title="PDF Preview" />
          ) : (
            <img src={previewUrl} alt="Preview" className="file-preview-img" />
          )}
          <button
            className="draw-action-btn"
            style={{ position: 'absolute', top: 4, right: 4 }}
            onClick={handleClear}
            title="Remove"
          >✕</button>
        </ResizablePreview>
      ) : (
        <div className="file-preview-empty">
          <span className="file-preview-placeholder">{placeholder}</span>
        </div>
      )}
      <div className="file-upload-actions">
        <button className="text-btn text-btn--secondary" onClick={() => inputRef.current?.click()} title="Select file">
          📁 File
        </button>
        <button className="text-btn text-btn--secondary" onClick={handlePaste} title="Paste from clipboard">
          📋 Paste
        </button>
        <button className="text-btn text-btn--secondary" onClick={() => cameraRef.current?.click()} title="Take photo">
          📷 Camera
        </button>
      </div>
      <input ref={inputRef} type="file" accept={accept} hidden onChange={handleSelect} />
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden onChange={handleSelect} />
    </div>
  )
}
