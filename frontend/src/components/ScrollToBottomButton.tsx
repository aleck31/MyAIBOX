import { IconArrowDown } from './icons'

/**
 * Round "jump to the latest message" button, floating at the bottom centre of a scrolling transcript.
 * Place it as the last child of the scroll container; it stays pinned to the visible bottom edge.
 */
export default function ScrollToBottomButton({ visible, onClick }: { visible: boolean; onClick: () => void }) {
  return (
    <div className="scroll-to-bottom-anchor">
      <button
        type="button"
        className={`scroll-to-bottom${visible ? ' is-visible' : ''}`}
        onClick={onClick}
        aria-label="Scroll to the latest message"
        title="Scroll to the latest message"
        tabIndex={visible ? 0 : -1}
        aria-hidden={!visible}
      >
        <IconArrowDown size={18} aria-hidden="true" />
      </button>
    </div>
  )
}
