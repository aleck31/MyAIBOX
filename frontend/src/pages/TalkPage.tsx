import { useEffect, useState } from 'react'
import { useParams, Navigate } from 'react-router-dom'
import { getTalkAgent, type TalkAgent } from '../api/client'
import TalkContainer from '../components/TalkContainer'

/** Route: /talk/:agentId — one realtime voice session per agent. */
export default function TalkPage() {
  const { agentId } = useParams<{ agentId: string }>()
  if (!agentId) return <Navigate to="/talk/english-coach" replace />
  return <TalkPageInner agentId={agentId} />
}

function TalkPageInner({ agentId }: { agentId: string }) {
  const [agent, setAgent] = useState<TalkAgent | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setAgent(null); setError(null)
    getTalkAgent(agentId).then(setAgent).catch(e => setError(e instanceof Error ? e.message : 'failed'))
  }, [agentId])

  if (error) {
    return (
      <div className="state-screen">
        <div style={{ color: '#e07070', textAlign: 'center' }}>
          <p style={{ fontWeight: 600 }}>Failed to load voice agent</p>
          <p style={{ fontSize: '13px', marginTop: '8px' }}>{error}</p>
        </div>
      </div>
    )
  }
  if (!agent) {
    return (
      <div className="state-screen">
        <div className="state-spinner"><div className="spinner-ring" /><span className="state-text">Loading</span></div>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* key by id so per-agent state (transcript, voice pref) initializes cleanly per agent */}
      <TalkContainer key={agent.id} agent={agent} />
    </div>
  )
}
