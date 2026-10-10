import { useEffect, type RefObject } from 'react'

/**
 * Marks a horizontally scrollable element with `data-fade-end` while more content is hidden past its
 * right edge, so CSS can fade that edge out and hint that it scrolls. Sets a DOM attribute instead of
 * React state: it changes on every scroll tick and should not re-render the page.
 */
export function useOverflowFade(ref: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const el = ref.current
    if (!el) return

    const update = () => {
      const hiddenOnRight = el.scrollWidth - el.clientWidth - el.scrollLeft > 1
      el.toggleAttribute('data-fade-end', hiddenOnRight)
    }

    update()
    el.addEventListener('scroll', update, { passive: true })
    // Size changes come from the window, and from children whose width changes (e.g. a select
    // whose options just loaded), so watch the children as well as the bar itself.
    const resize = new ResizeObserver(update)
    resize.observe(el)
    const watchChildren = () => Array.from(el.children).forEach(child => resize.observe(child))
    watchChildren()
    const mutation = new MutationObserver(() => { watchChildren(); update() })
    mutation.observe(el, { childList: true })

    return () => {
      el.removeEventListener('scroll', update)
      resize.disconnect()
      mutation.disconnect()
    }
  }, [ref])
}
