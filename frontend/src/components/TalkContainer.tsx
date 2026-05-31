import { useCallback, useEffect, useRef, useState } from 'react'
import { useTalk } from '../hooks/useTalk'
import { useStoredState } from '../hooks/useStoredState'
import { resolveDefaultModel } from '../utils/model'
import ModelSelector, { type ModelOption } from './ModelSelector'
import { getTalkConfig, clearTalkSession } from '../api/client'
import { IconMic, IconClose, IconTrash } from './icons'
import type { TalkAgent } from '../api/client'

interface Turn { role: 'user' | 'assistant'; text: string; final: boolean }
interface Voice { id: string; name: string }

// Transcript persists per-tab until the user clears it (the universal "no clear =
// it stays" rule) — survives route switches, matching the back-end session cache.
const turnsKey = (agentId: string) => `talk-turns:${agentId}`
function loadTurns(agentId: string): Turn[] {
  try { return JSON.parse(sessionStorage.getItem(turnsKey(agentId)) || '[]') } catch { return [] }
}

/** Realtime voice call with one agent. Follows the chat layout convention
 *  (assistant-layout + section-bar with module-level options + conversation
 *  column), but the body is voice-transcript bubbles and the bottom is call
 *  control. Section bar holds: model selector, voice picker, clear. */
export default function TalkContainer({ agent }: { agent: TalkAgent }) {
  const [turns, setTurns] = useState<Turn[]>(() => loadTurns(agent.id))
  const [error, setError] = useState<string | null>(null)
  const [models, setModels] = useState<ModelOption[]>([])
  const [voices, setVoices] = useState<Voice[]>([])
  // Top-bar model + voice are per-agent UI preferences (ARD 001): persist in
  // localStorage, defaulting to the agent's (override-merged) value. Priority:
  // user pick → agent override → module default → first eligible (resolveDefaultModel).
  const [modelId, setModelId] = useStoredState(`talk-model:${agent.id}`, agent.default_model ?? '')
  const [voice, setVoice] = useStoredState(`talk-voice:${agent.id}`, agent.voice_id)
  const threadRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getTalkConfig().then(cfg => {
      const opts = cfg.models.map(m => ({ model_id: m.model_id, name: m.name }))
      setModels(opts)
      setVoices(cfg.voices)
      // Only fill when the user hasn't picked and the agent had no override default.
      setModelId(prev => prev || resolveDefaultModel(opts, agent.default_model ?? cfg.default_model))
    }).catch(() => { /* best-effort */ })
  }, [agent.default_model])

  // Persist transcript per-tab so a route switch (then back) keeps it.
  useEffect(() => {
    sessionStorage.setItem(turnsKey(agent.id), JSON.stringify(turns))
  }, [turns, agent.id])

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

  // Clear = front-end wipes transcript AND back-end forgets, so the two stay
  // consistent (user clears → agent loses memory; otherwise history persists).
  const handleClear = useCallback(() => {
    setTurns([])
    clearTalkSession(agent.id).catch(() => { /* best-effort */ })
  }, [agent.id])

  return (
    <div className="assistant-layout">
      <div className="assistant-chat-col">
        <div className="section-bar">
          <ModelSelector models={models} value={modelId} onChange={setModelId} disabled={talk.connected} />
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
              onClick={() => talk.connect({ voiceId: voice, modelId, history: turns.map(t => ({ role: t.role, text: t.text })) })}>
              <IconMic size={20} /> {talk.connecting ? 'Connecting…' : 'Start call'}
            </button>
          ) : (
            <>
              <button className="talk-call-btn talk-call-btn--end" onClick={talk.hangup}>
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
