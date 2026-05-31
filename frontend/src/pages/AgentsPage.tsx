import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  listChatAgents,
  listChatTools,
  listChatSkills,
  getMcpServers,
  listChatAgentModels,
  patchChatAgent,
  resetChatAgent,
  listTalkAgents,
  listTalkAgentModels,
  getTalkConfig,
  patchTalkAgent,
  resetTalkAgent,
  type ChatAgent,
  type ChatToolInfo,
  type TalkAgent,
} from '../api/client'
import AgentCard from '../components/AgentCard'
import LiveAgentCard from '../components/LiveAgentCard'

interface ModelOpt { model_id: string; name: string; reasoning?: boolean }
interface NameDesc { name: string; description: string }
interface Voice { id: string; name: string }

export default function AgentsPage() {
  const [agents, setAgents] = useState<ChatAgent[]>([])
  const [models, setModels] = useState<ModelOpt[]>([])
  const [tools, setTools] = useState<{ legacy: ChatToolInfo[]; builtin: ChatToolInfo[] }>({ legacy: [], builtin: [] })
  const [skills, setSkills] = useState<NameDesc[]>([])
  const [mcp, setMcp] = useState<Array<{ name: string; disabled: boolean }>>([])
  // Voice (Talk-with-Agent) agents share this page but have their own config surface.
  const [talkAgents, setTalkAgents] = useState<TalkAgent[]>([])
  const [talkModels, setTalkModels] = useState<ModelOpt[]>([])
  const [voices, setVoices] = useState<Voice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [a, m, t, s, servers, ta, tm, tcfg] = await Promise.all([
        listChatAgents(),
        listChatAgentModels(),
        listChatTools(),
        listChatSkills(),
        getMcpServers(),
        listTalkAgents(),
        listTalkAgentModels(),
        getTalkConfig(),
      ])
      setAgents(a.agents)
      setModels(m.models || [])
      setTools(t)
      setSkills(s.skills || [])
      setMcp(
        Array.isArray(servers)
          ? servers.map((x: any) => ({ name: x.name, disabled: !!x.disabled }))
          : [],
      )
      setTalkAgents(ta.agents)
      setTalkModels(tm.models || [])
      setVoices(tcfg.voices || [])
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

  const handleTalkSave = useCallback(async (agentId: string, patch: Partial<TalkAgent>) => {
    const updated = await patchTalkAgent(agentId, patch)
    setTalkAgents(prev => prev.map(a => (a.id === agentId ? updated : a)))
  }, [])

  const handleTalkReset = useCallback(async (agentId: string) => {
    const updated = await resetTalkAgent(agentId)
    setTalkAgents(prev => prev.map(a => (a.id === agentId ? updated : a)))
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
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>Agent settings</span>
        <div className="section-actions">
          <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>
            {agents.length + talkAgents.length} agents
          </span>
        </div>
      </div>
      <div className="settings-content">
        <div className="settings-section" style={{ gap: 10 }}>
          <div className="settings-group-label">Chat agents</div>
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

          {talkAgents.length > 0 && (
            <>
              <div className="settings-group-label" style={{ marginTop: 8 }}>Voice agents</div>
              {talkAgents.map((agent) => (
                <LiveAgentCard
                  key={agent.id}
                  agent={agent}
                  models={talkModels}
                  voices={voices}
                  legacyTools={tools.legacy}
                  onSave={(patch) => handleTalkSave(agent.id, patch)}
                  onReset={() => handleTalkReset(agent.id)}
                />
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
