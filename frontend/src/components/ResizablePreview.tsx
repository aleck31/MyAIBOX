import { useRef, useCallback, useState } from 'react'

interface Props {
  height?: number | string
  minHeight?: number
  children: React.ReactNode
  className?: string
}

export default function ResizablePreview({ height: defaultHeight, minHeight = 150, children, className }: Props) {
  const [height, setHeight] = useState<number | string | null>(defaultHeight ?? null)
  const containerRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)
  const startY = useRef(0)
  const startH = useRef(0)

  const onStart = useCallback((clientY: number) => {
    dragging.current = true
    startY.current = clientY
    startH.current = containerRef.current?.clientHeight ?? 400
    document.body.style.userSelect = 'none'
  }, [])

  const onMove = useCallback((clientY: number) => {
    if (!dragging.current) return
    const newH = Math.max(minHeight, startH.current + clientY - startY.current)
    setHeight(newH)
  }, [minHeight])

  const onEnd = useCallback(() => {
    dragging.current = false
    document.body.style.userSelect = ''
  }, [])

  return (
    <div ref={containerRef} className={`file-preview ${className ?? ''}`} style={{ height: height ?? '100%' }}>
      {children}
      <div
        className="resize-handle"
        onMouseDown={e => { onStart(e.clientY); const move = (ev: MouseEvent) => onMove(ev.clientY); const up = () => { onEnd(); window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }; window.addEventListener('mousemove', move); window.addEventListener('mouseup', up) }}
        onTouchStart={e => { onStart(e.touches[0].clientY); const move = (ev: TouchEvent) => onMove(ev.touches[0].clientY); const up = () => { onEnd(); window.removeEventListener('touchmove', move); window.removeEventListener('touchend', up) }; window.addEventListener('touchmove', move, { passive: true }); window.addEventListener('touchend', up) }}
      />
    </div>
  )
}
