import { useRef, type HTMLAttributes } from 'react'
import { useOverflowFade } from '../hooks/useOverflowFade'

/**
 * Shared top bar of every module. On narrow screens it scrolls sideways; while controls are hidden
 * past the right edge that edge fades out (see `.section-bar[data-fade-end]`) so the scroll is discoverable.
 */
export default function SectionBar({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  const ref = useRef<HTMLDivElement>(null)
  useOverflowFade(ref)
  return <div ref={ref} className={className ? `section-bar ${className}` : 'section-bar'} {...rest} />
}
