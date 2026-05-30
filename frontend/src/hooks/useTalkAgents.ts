import { useEffect, useState } from 'react'
import { listTalkAgents, type TalkAgent } from '../api/client'

/** Built-in voice agents for the "Talk with Agent" sidebar group. */
export function useTalkAgents() {
  const [agents, setAgents] = useState<TalkAgent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listTalkAgents()
      .then(({ agents }) => setAgents(agents))
      .catch(() => { /* best-effort; group just stays empty */ })
      .finally(() => setLoading(false))
  }, [])

  return { agents, loading }
}
