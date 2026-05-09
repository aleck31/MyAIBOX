import { useEffect, useState } from 'react'
import { useParams, Navigate } from 'react-router-dom'
import { useChatSession } from '../hooks/useChatSession'
import { getModels } from '../api/client'
import ChatContainer from '../components/ChatContainer'
import type { ModelOption } from '../components/ModelSelector'

/** Route: /chat/:agentId — one container per agent. */
export default function ChatPage() {
  const { agentId } = useParams<{ agentId: string }>()
  if (!agentId) return <Navigate to="/chat/assistant" replace />
  return <ChatPageInner agentId={agentId} />
}

function ChatPageInner({ agentId }: { agentId: string }) {
  const { agent, session, loading, error } = useChatSession(agentId)
  const [models, setModels] = useState<ModelOption[]>([])

  useEffect(() => {
    getModels()
      .then((list: Array<{ model_id: string; name: string; api_provider?: string }>) => {
        setModels(list.map(m => ({ model_id: m.model_id, name: m.api_provider ? `${m.name}, ${m.api_provider}` : m.name })))
      })
      .catch(() => { /* models list is best-effort */ })
  }, [])

  if (loading) {
    return (
      <div className="state-screen">
        <div className="state-spinner">
          <div className="spinner-ring" />
          <span className="state-text">Loading</span>
        </div>
      </div>
    )
  }

  if (error || !agent || !session) {
    return (
      <div className="state-screen">
        <div style={{ color: '#e07070', textAlign: 'center' }}>
          <p style={{ fontWeight: 600 }}>Failed to load agent</p>
          <p style={{ fontSize: '13px', marginTop: '8px' }}>{error ?? `Unknown agent: ${agentId}`}</p>
        </div>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <ChatContainer agent={agent} session={session} models={models} />
    </div>
  )
}
