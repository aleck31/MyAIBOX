import { useCallback, useEffect, useRef, useState } from 'react'
import { useTalk } from '../hooks/useTalk'
import { useConfirm } from './ConfirmDialog'
import ModelSelector, { type ModelOption } from './ModelSelector'
import { getTalkConfig } from '../api/client'
import { IconMic, IconClose, IconTrash } from './icons'
import type { TalkAgent } from '../api/client'

interface Turn { role: 'user' | 'assistant'; text: string; final: boolean }
interface Voice { id: string; name: string }

/** Realtime voice call with one agent. Follows the chat layout convention
 *  (assistant-layout + section-bar with module-level options + conversation
 *  column), but the body is voice-transcript bubbles and the bottom is call
 *  control. Section bar holds: model selector, voice picker, clear. */
export default function TalkContainer({ agent }: { agent: TalkAgent }) {
  const confirm = useConfirm()
  const [turns, setTurns] = useState<Turn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [models, setModels] = useState<ModelOption[]>([])
  const [modelId, setModelId] = useState('')
  const [voices, setVoices] = useState<Voice[]>([])
  const [voice, setVoice] = useState(agent.voice_id || 'matthew')
  const threadRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getTalkConfig().then(cfg => {
      setModels(cfg.models.map(m => ({ model_id: m.model_id, name: m.name })))
      setModelId(cfg.default_model)
      setVoices(cfg.voices)
    }).catch(() => { /* best-effort */ })
  }, [])

  const onTranscript = useCallback((text: string, role: 'user' | 'assistant', final: boolean) => {
    setTurns(prev => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last && last.role === role && !last.final) next[next.length - 1] = { role, text, final }
      else next.push({ role, text, final })
      return next
    })
    queueMicrotask(() => threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight }))
  }, [])

  const talk = useTalk(agent.id, { onTranscript, onError: setError, onClose: () => setError(null) })

  const handleHangup = useCallback(async () => {
    if (!(await confirm({ title: 'End call', message: `End the voice session with ${agent.name}?`, confirmLabel: 'Hang up', danger: true }))) return
    talk.hangup()
  }, [confirm, agent.name, talk])

  const handleClear = useCallback(() => setTurns([]), [])

  return (
    <div className="assistant-layout">
      <div className="assistant-chat-col">
        <div className="section-bar">
          <ModelSelector models={models} value={modelId} onChange={setModelId} />
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select className="select" value={voice} onChange={e => setVoice(e.target.value)}
              disabled={talk.connected} title="Voice">
              {voices.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
            <button className="bar-icon-btn bar-icon-btn--danger" onClick={handleClear}
              disabled={!turns.length} title="Clear transcript">
              <IconTrash size={14} />
            </button>
          </div>
        </div>

        <div className="talk-thread" ref={threadRef}>
          {turns.length === 0 ? (
            <div className="talk-thread-empty">{agent.description}</div>
          ) : (
            turns.map((t, i) => (
              <div key={i} className={`talk-bubble talk-bubble--${t.role}${t.final ? '' : ' talk-bubble--partial'}`}>
                {t.text}
              </div>
            ))
          )}
          {error && <div className="talk-error">{error}</div>}
        </div>

        <div className="talk-controls">
          {!talk.connected ? (
            <button className="talk-call-btn talk-call-btn--start" disabled={talk.connecting}
              onClick={() => { setTurns([]); talk.connect(voice) }}>
              <IconMic size={20} /> {talk.connecting ? 'Connecting…' : 'Start call'}
            </button>
          ) : (
            <>
              <button className="talk-call-btn talk-call-btn--end" onClick={handleHangup}>
                <IconClose size={20} /> Hang up
              </button>
              <span className={`talk-mic-indicator${talk.speaking ? '' : ' talk-mic-indicator--live'}`} aria-hidden />
              <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>
                {talk.speaking ? 'Speaking…' : 'Listening…'}
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
