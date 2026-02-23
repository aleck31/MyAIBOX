import type { AttachmentAdapter, PendingAttachment, CompleteAttachment } from '@assistant-ui/react'

const ACCEPT = 'image/jpeg,image/png,image/gif,image/webp,application/pdf,.csv,.doc,.docx,.xls,.xlsx,.txt,.md,video/mp4,video/webm,video/quicktime'

async function uploadFile(file: File): Promise<{ path: string; name: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/upload', { method: 'POST', body: form, credentials: 'include' })
  const data = await res.json()
  if (!data.ok) throw new Error(data.error || 'Upload failed')
  return { path: data.path, name: data.name }
}

export class FileUploadAdapter implements AttachmentAdapter {
  accept = ACCEPT

  async add({ file }: { file: File }): Promise<PendingAttachment> {
    if (file.size > 20 * 1024 * 1024) {
      throw new Error('File size exceeds 20MB limit')
    }
    // Read data URL for frontend preview
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const r = new FileReader()
      r.onload = () => resolve(r.result as string)
      r.onerror = reject
      r.readAsDataURL(file)
    })
    return {
      id: crypto.randomUUID(),
      type: file.type.startsWith('image/') ? 'image' : 'document',
      name: file.name,
      file,
      contentType: file.type,
      content: [
        file.type.startsWith('image/')
          ? { type: 'image' as const, image: dataUrl }
          : { type: 'file' as const, data: dataUrl, mimeType: file.type, filename: file.name },
      ],
      status: { type: 'running', reason: 'uploading', progress: 0 },
    }
  }

  async send(attachment: PendingAttachment): Promise<CompleteAttachment> {
    const { path } = await uploadFile(attachment.file)
    return {
      id: attachment.id,
      type: attachment.type as 'image' | 'document' | 'file',
      name: attachment.name,
      contentType: attachment.file.type,
      content: [
        // Server path for backend, keep preview content from add()
        { type: 'file' as const, data: path, mimeType: attachment.file.type },
        // Preserve the preview content
        ...(attachment.content ?? []),
      ],
      status: { type: 'complete' },
    }
  }

  async remove(): Promise<void> {}
}
