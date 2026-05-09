import { useEffect, useState } from 'react'
import { getChatAgent, getChatSession, type ChatAgent, type ChatSession } from '../api/client'

/** Load agent definition + per-agent session snapshot in parallel. */
export function useChatSession(agentId: string) {
  const [agent, setAgent] = useState<ChatAgent | null>(null)
  const [session, setSession] = useState<ChatSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setAgent(null)
    setSession(null)
    setError(null)
    Promise.all([getChatAgent(agentId), getChatSession(agentId)])
      .then(([a, s]) => {
        if (cancelled) return
        setAgent(a)
        setSession(s)
      })
      .catch(e => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load agent')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [agentId])

  return { agent, session, loading, error }
}
