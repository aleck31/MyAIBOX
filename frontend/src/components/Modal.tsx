import { ReactNode, useEffect } from 'react'

/**
 * Modal primitive. Renders a centered card over a scrim overlay.
 *
 * - Click the overlay → onClose
 * - ESC key → onClose
 * - Clicks inside the card do not bubble to the overlay
 * - Page scroll is locked while open
 *
 * CSS classes live in index.css: `.overlay` + `.modal`.
 * On mobile (<768px) the card goes near full-screen.
 */
export interface ModalProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  className?: string
}

export function Modal({ open, onClose, children, className }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="overlay" onClick={onClose}>
      <div
        className={['modal', className].filter(Boolean).join(' ')}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}

/** Flex-end action row — lives inside <Modal> children. */
export function ModalActions({ children }: { children: ReactNode }) {
  return <div className="modal-actions">{children}</div>
}
