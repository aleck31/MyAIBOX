import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { Modal, ModalActions } from './Modal'
import { Button } from './Button'

interface ConfirmOptions {
  title?: string
  message: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean   // red confirm button for destructive actions
}

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>

const ConfirmContext = createContext<ConfirmFn | null>(null)

/** App-level provider exposing an async confirm() that renders a styled Modal
 *  instead of the browser's native confirm() (off-brand + poor on mobile). */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null)
  const [resolver, setResolver] = useState<((v: boolean) => void) | null>(null)

  const confirm = useCallback<ConfirmFn>((o) => {
    setOpts(o)
    return new Promise<boolean>((resolve) => setResolver(() => resolve))
  }, [])

  const finish = useCallback((v: boolean) => {
    resolver?.(v)
    setResolver(null)
    setOpts(null)
  }, [resolver])

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Modal open={!!opts} onClose={() => finish(false)} className="modal--confirm">
        {opts && (
          <>
            {opts.title && <h3 className="modal-title">{opts.title}</h3>}
            <div className="modal-message">{opts.message}</div>
            <ModalActions>
              <Button onClick={() => finish(false)}>{opts.cancelLabel ?? 'Cancel'}</Button>
              <Button variant={opts.danger ? 'danger' : 'primary'} onClick={() => finish(true)} autoFocus>
                {opts.confirmLabel ?? 'Confirm'}
              </Button>
            </ModalActions>
          </>
        )}
      </Modal>
    </ConfirmContext.Provider>
  )
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm must be used within <ConfirmProvider>')
  return ctx
}
