import { useCallback, useEffect, useState } from 'react'
import { listChatAgents, type ChatAgent } from '../api/client'

/**
 * Global-ish list of all built-in chat agents, with user overrides applied.
 * The sidebar and any agent selector consume this hook; fetched once per
 * session and refreshable after an edit.
 */
export function useChatAgents() {
  const [agents, setAgents] = useState<ChatAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const { agents } = await listChatAgents()
      setAgents(agents)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load agents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { reload() }, [reload])

  return { agents, loading, error, reload }
}
