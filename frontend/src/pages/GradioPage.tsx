import { useLocation } from 'react-router-dom'

// Maps module key to the tab label in Gradio's TabbedInterface
// Gradio 6 deep-links via URL hash: /main#tab-<label>
const TAB_ANCHORS: Record<string, string> = {
  assistant: 'assistant-🤖',
  text:      'text-📝',
  summary:   'summary-📰',
  vision:    'vision-👀',
  asking:    'asking-🤔',
  coding:    'coding-💻',
  draw:      'draw-🎨',
  settings:  'settings-⚙️',
}

export default function GradioPage() {
  const location = useLocation()
  const module = (location.state as { module?: string } | null)?.module

  // Build Gradio URL — attempt tab deep-link; falls back to /main root
  const anchor = module ? TAB_ANCHORS[module] : undefined
  const src = anchor ? `/main#${anchor}` : '/main'

  return (
    <div className="gradio-frame-wrapper">
      <iframe
        key={src}          /* remount on anchor change */
        className="gradio-frame"
        src={src}
        title={module ? `${module} module` : 'AI Box'}
        allow="camera; microphone"
      />
    </div>
  )
}
