import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  listChatAgents,
  listChatTools,
  listChatSkills,
  getMcpServers,
  getModels,
  patchChatAgent,
  resetChatAgent,
  type ChatAgent,
  type ChatToolInfo,
} from '../api/client'
import AgentCard from '../components/AgentCard'

interface ModelOpt { model_id: string; name: string }
interface NameDesc { name: string; description: string }

export default function AgentsPage() {
  const [agents, setAgents] = useState<ChatAgent[]>([])
  const [models, setModels] = useState<ModelOpt[]>([])
  const [tools, setTools] = useState<{ legacy: ChatToolInfo[]; builtin: ChatToolInfo[] }>({ legacy: [], builtin: [] })
  const [skills, setSkills] = useState<NameDesc[]>([])
  const [mcp, setMcp] = useState<Array<{ name: string; disabled: boolean }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [a, m, t, s, servers] = await Promise.all([
        listChatAgents(),
        getModels(),
        listChatTools(),
        listChatSkills(),
        getMcpServers(),
      ])
      setAgents(a.agents)
      setModels(
        (m || []).map((x: any) => ({
          model_id: x.model_id,
          name: x.api_provider ? `${x.name}, ${x.api_provider}` : x.name,
        })),
      )
      setTools(t)
      setSkills(s.skills || [])
      setMcp(
        Array.isArray(servers)
          ? servers.map((x: any) => ({ name: x.name, disabled: !!x.disabled }))
          : [],
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load agents settings')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { reload() }, [reload])

  const handleSave = useCallback(async (agentId: string, patch: Partial<ChatAgent>) => {
    const updated = await patchChatAgent(agentId, patch)
    setAgents(prev => prev.map(a => (a.id === agentId ? updated : a)))
  }, [])

  const handleReset = useCallback(async (agentId: string) => {
    const updated = await resetChatAgent(agentId)
    setAgents(prev => prev.map(a => (a.id === agentId ? updated : a)))
  }, [])

  const mcpServers = useMemo(() => mcp.map(m => m.name), [mcp])

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

  if (error) {
    return (
      <div className="state-screen">
        <div style={{ color: '#e07070', textAlign: 'center' }}>
          <p style={{ fontWeight: 600 }}>Failed to load</p>
          <p style={{ fontSize: 13, marginTop: 8 }}>{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="settings-panel">
      <div className="section-bar">
        <span style={{ fontSize: 13, fontWeight: 600 }}>Agent settings</span>
        <div className="section-actions">
          <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>
            {agents.length} agents
          </span>
        </div>
      </div>
      <div className="settings-content">
        <div className="settings-section" style={{ gap: 10 }}>
          {agents.map((agent, idx) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              defaultOpen={idx === 0}
              models={models}
              legacyTools={tools.legacy}
              builtinTools={tools.builtin}
              mcpServers={mcpServers}
              skills={skills}
              onSave={(patch) => handleSave(agent.id, patch)}
              onReset={() => handleReset(agent.id)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
