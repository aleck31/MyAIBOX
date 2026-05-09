import { useCallback, useRef, useState } from 'react'
import {
  chatStreamUrl,
  clearChatHistory,
  syncChatHistory,
  updateChatCloudSync,
  updateChatModel,
  type ChatAgent,
  type ChatSession,
} from '../api/client'
import { clearRuntimeCache } from '../hooks/useAGUIRuntime'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { useStoredState } from '../hooks/useStoredState'
import ModelSelector, { type ModelOption } from './ModelSelector'
import ChatWindow, { type ChatWindowHandle } from './ChatWindow'
import WorkspacePanel, { type WorkspacePanelHandle } from './workspace/WorkspacePanel'

interface Props {
  agent: ChatAgent
  session: ChatSession
  models: ModelOption[]
}

export default function ChatContainer({ agent, session, models }: Props) {
  const [modelId, setModelId] = useState(session.model_id || agent.default_model || '')
  const [cloudSync, setCloudSync] = useState(session.cloud_sync ?? false)
  const [syncing, setSyncing] = useState(false)
  const [syncDone, setSyncDone] = useState(false)
  const [chatKey, setChatKey] = useState(0)
  const [chatHistory, setChatHistory] = useState(session.history || [])
  const [workspaceOpen, setWorkspaceOpen] = useStoredState(
    `chat-workspace-open:${agent.id}`,
    false,
  )
  const chatRef = useRef<ChatWindowHandle>(null)
  const workspaceRef = useRef<WorkspacePanelHandle>(null)

  const isDesktop = useMediaQuery('(min-width: 1280px)')
  const isTablet = useMediaQuery('(min-width: 1024px) and (max-width: 1279.9px)')
  const layoutMode: 'side' | 'overlay' | 'modal' =
    isDesktop ? 'side' : isTablet ? 'overlay' : 'modal'

  const handleModelChange = useCallback(async (newModelId: string) => {
    setModelId(newModelId)
    try { await updateChatModel(agent.id, newModelId) } catch (err) { console.error(err) }
  }, [agent.id])

  const handleCloudSyncToggle = useCallback(async () => {
    const next = !cloudSync
    setCloudSync(next)
    try { await updateChatCloudSync(agent.id, next) } catch (err) { console.error(err) }
  }, [cloudSync, agent.id])

  const handleSync = useCallback(async () => {
    const messages = chatRef.current?.getMessages() ?? []
    setSyncing(true)
    setSyncDone(false)
    try {
      await syncChatHistory(agent.id, messages)
      setSyncDone(true)
      setTimeout(() => setSyncDone(false), 2000)
    } catch (err) {
      console.error('Sync failed:', err)
    } finally {
      setSyncing(false)
    }
  }, [agent.id])

  const handleClear = useCallback(async () => {
    clearRuntimeCache(session.session_id)
    setChatHistory([])
    setChatKey(k => k + 1)
    try { await clearChatHistory(agent.id) } catch (err) { console.error('Clear failed:', err) }
  }, [agent.id, session.session_id])

  const toggleWorkspace = useCallback(() => {
    setWorkspaceOpen(o => {
      const next = !o
      if (next) setTimeout(() => workspaceRef.current?.refresh(), 0)
      return next
    })
  }, [setWorkspaceOpen])

  const closeWorkspace = useCallback(() => setWorkspaceOpen(false), [setWorkspaceOpen])

  const [sideWidth, setSideWidth] = useStoredState('chat-workspace-width', 420)
  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = sideWidth
    const onMove = (ev: MouseEvent) => {
      const w = Math.max(320, Math.min(900, startW - (ev.clientX - startX)))
      setSideWidth(w)
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      document.body.style.userSelect = ''
    }
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [sideWidth, setSideWidth])

  const handleCustomEvent = useCallback((name: string) => {
    if (name === 'workspace_updated') workspaceRef.current?.refresh()
  }, [])

  const workspacePanel = (
    <WorkspacePanel
      ref={workspaceRef}
      agentId={agent.id}
      onClose={layoutMode !== 'side' ? closeWorkspace : undefined}
    />
  )

  return (
    <div className="assistant-layout">
      <div className="assistant-chat-col">
        <div className="section-bar">
          <span className="chat-agent-title" title={agent.description}>
            <span className="chat-agent-avatar">{agent.avatar}</span>
            {agent.name}
          </span>
          <ModelSelector
            models={models}
            value={modelId}
            onChange={handleModelChange}
          />
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
            <button
              className="bar-icon-btn bar-icon-btn--danger"
              onClick={handleClear}
              disabled={syncing}
              title="Clear conversation"
            >
              🗑
            </button>
            {!cloudSync && (
              <button
                className={`bar-icon-btn${syncDone ? ' done' : ''}`}
                onClick={handleSync}
                disabled={syncing}
                title="Sync to cloud"
              >
                {syncing ? '⏳' : syncDone ? '✓' : '📤'}
              </button>
            )}
            <button
              className={`bar-icon-btn${cloudSync ? ' active' : ''}`}
              onClick={handleCloudSyncToggle}
              title={cloudSync ? 'Auto-sync ON (click to disable)' : 'Auto-sync OFF (click to enable)'}
            >
              ☁️
            </button>
            {agent.workspace_enabled && (
              <button
                className={`bar-icon-btn${workspaceOpen ? ' active' : ''}`}
                onClick={toggleWorkspace}
                title="Workspace"
              >
                📁
              </button>
            )}
          </div>
        </div>

        <ChatWindow
          key={chatKey}
          ref={chatRef}
          threadId={session.session_id}
          initialHistory={chatHistory}
          url={chatStreamUrl}
          onCustomEvent={handleCustomEvent}
          forwardedProps={{ agent_id: agent.id }}
          onMessagesEdited={(msgs) => { syncChatHistory(agent.id, msgs).catch(() => {}) }}
        />
      </div>

      {agent.workspace_enabled && workspaceOpen && layoutMode === 'side' && (
        <div
          className="assistant-workspace assistant-workspace--side"
          style={{ flex: `0 0 ${sideWidth}px` }}
        >
          <div className="assistant-workspace-resizer" onMouseDown={onResizeStart} />
          {workspacePanel}
        </div>
      )}

      {agent.workspace_enabled && workspaceOpen && layoutMode === 'overlay' && (
        <>
          <div className="assistant-workspace-backdrop" onClick={closeWorkspace} />
          <div className="assistant-workspace assistant-workspace--overlay">
            {workspacePanel}
          </div>
        </>
      )}

      {agent.workspace_enabled && workspaceOpen && layoutMode === 'modal' && (
        <div className="overlay" onClick={closeWorkspace}>
          <div className="modal assistant-workspace--modal" onClick={e => e.stopPropagation()}>
            {workspacePanel}
          </div>
        </div>
      )}
    </div>
  )
}
