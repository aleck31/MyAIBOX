import { useCallback, useEffect, useRef, useState } from 'react'

/** Within this many pixels of the end counts as "at the latest message". */
const AT_BOTTOM_PX = 80

/**
 * Follow the newest content of a scrolling transcript, the way chat apps do: new content keeps the view at the
 * bottom only while the user is already there, so scrolling up to read something is not undone by the next
 * streamed token. `atBottom` drives the jump-to-latest button.
 *
 * Attach `ref` to the scroll container. It is a callback ref so that a container rendered later (after a
 * loading state) is still picked up.
 */
export function useStickToBottom() {
  const [el, setEl] = useState<HTMLElement | null>(null)
  const elRef = useRef<HTMLElement | null>(null)
  const [atBottom, setAtBottom] = useState(true)
  // Read by follow(): where the user was before the new content made the transcript longer.
  const atBottomRef = useRef(true)

  const ref = useCallback((node: HTMLElement | null) => { elRef.current = node; setEl(node) }, [])

  useEffect(() => {
    if (!el) return
    const update = () => {
      const value = el.scrollHeight - el.scrollTop - el.clientHeight <= AT_BOTTOM_PX
      atBottomRef.current = value
      setAtBottom(value)
    }
    update()
    el.addEventListener('scroll', update, { passive: true })
    const resize = new ResizeObserver(update)
    resize.observe(el)
    return () => { el.removeEventListener('scroll', update); resize.disconnect() }
  }, [el])

  const scrollToBottom = useCallback((smooth = true) => {
    const node = elRef.current
    if (node) node.scrollTo({ top: node.scrollHeight, behavior: smooth ? 'smooth' : 'instant' })
  }, [])

  /** Call after content was added: keeps following only if the user was at the bottom. */
  const follow = useCallback(() => {
    if (atBottomRef.current) scrollToBottom(false)
  }, [scrollToBottom])

  return { ref, atBottom, scrollToBottom, follow }
}
