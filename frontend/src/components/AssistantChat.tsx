import { useRef, useState, useCallback } from 'react'
import {
  updateAssistantModel,
  syncAssistantHistory,
  updateAssistantCloudSync,
  clearAssistantHistory,
} from '../api/client'
import { clearRuntimeCache } from '../hooks/useAGUIRuntime'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { useStoredState } from '../hooks/useStoredState'
import ModelSelector from './ModelSelector'
import ChatWindow, { type ChatWindowHandle } from './ChatWindow'
import WorkspacePanel, { type WorkspacePanelHandle } from './workspace/WorkspacePanel'
import type { AssistantConfig, AssistantPrefs } from '../types/assistant'

interface AssistantChatProps {
  config: AssistantConfig
  initialPrefs: AssistantPrefs
}

export default function AssistantChat({ config, initialPrefs }: AssistantChatProps) {
  const [modelId, setModelId] = useState(initialPrefs.model_id || '')
  const [cloudSync, setCloudSync] = useState(initialPrefs.cloud_sync ?? false)
  const [syncing, setSyncing] = useState(false)
  const [syncDone, setSyncDone] = useState(false)
  const [chatKey, setChatKey] = useState(0)
  const [chatHistory, setChatHistory] = useState(initialPrefs.history || [])
  const [workspaceOpen, setWorkspaceOpen] = useStoredState('assistant-workspace-open', false)
  const chatRef = useRef<ChatWindowHandle>(null)
  const workspaceRef = useRef<WorkspacePanelHandle>(null)

  // Layout mode: side ≥ 1280px, overlay 1024-1279px, modal < 1024px.
  const isDesktop = useMediaQuery('(min-width: 1280px)')
  const isTablet = useMediaQuery('(min-width: 1024px) and (max-width: 1279.9px)')
  const layoutMode: 'side' | 'overlay' | 'modal' =
    isDesktop ? 'side' : isTablet ? 'overlay' : 'modal'

  const handleModelChange = useCallback(async (newModelId: string) => {
    setModelId(newModelId)
    try { await updateAssistantModel(newModelId) } catch (err) { console.error(err) }
  }, [])

  const handleCloudSyncToggle = useCallback(async () => {
    const next = !cloudSync
    setCloudSync(next)
    try { await updateAssistantCloudSync(next) } catch (err) { console.error(err) }
  }, [cloudSync])

  const handleSync = useCallback(async () => {
    const messages = chatRef.current?.getMessages() ?? []
    setSyncing(true)
    setSyncDone(false)
    try {
      await syncAssistantHistory(messages)
      setSyncDone(true)
      setTimeout(() => setSyncDone(false), 2000)
    } catch (err) {
      console.error('Sync failed:', err)
    } finally {
      setSyncing(false)
    }
  }, [])

  const handleClear = useCallback(async () => {
    clearRuntimeCache(initialPrefs.session_id)
    setChatHistory([])
    setChatKey(k => k + 1)
    try { await clearAssistantHistory() } catch (err) { console.error('Clear failed:', err) }
  }, [initialPrefs.session_id])

  const toggleWorkspace = useCallback(() => {
    setWorkspaceOpen(o => {
      const next = !o
      // Re-list when opening — catches files the agent wrote while closed.
      if (next) setTimeout(() => workspaceRef.current?.refresh(), 0)
      return next
    })
  }, [setWorkspaceOpen])

  // Persist side-panel width across sessions. Tablet overlay / mobile modal
  // have fixed sizing; only the desktop side panel is user-resizable.
  const [sideWidth, setSideWidth] = useStoredState('assistant-workspace-width', 420)
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

  const closeWorkspace = useCallback(() => setWorkspaceOpen(false), [setWorkspaceOpen])

  // Backend emits `workspace_updated` CUSTOM events after every tool call.
  // Refresh the file list whenever one arrives; the panel doesn't need to
  // be open — it keeps its state fresh for the next toggle.
  const handleCustomEvent = useCallback((name: string) => {
    if (name === 'workspace_updated') workspaceRef.current?.refresh()
  }, [])

  const workspacePanel = <WorkspacePanel ref={workspaceRef} onClose={layoutMode !== 'side' ? closeWorkspace : undefined} />

  return (
    <div className="assistant-layout">
      <div className="assistant-chat-col">
        <div className="section-bar">
          <ModelSelector
            models={config.models}
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
              {cloudSync ? '☁️' : '☁️'}
            </button>
            <button
              className={`bar-icon-btn${workspaceOpen ? ' active' : ''}`}
              onClick={toggleWorkspace}
              title="Workspace"
            >
              📁
            </button>
          </div>
        </div>

        <ChatWindow
          key={chatKey}
          ref={chatRef}
          threadId={initialPrefs.session_id}
          initialHistory={chatHistory}
          url="/api/assistant/chat"
          onCustomEvent={handleCustomEvent}
        />
      </div>

      {workspaceOpen && layoutMode === 'side' && (
        <div
          className="assistant-workspace assistant-workspace--side"
          style={{ flex: `0 0 ${sideWidth}px` }}
        >
          <div className="assistant-workspace-resizer" onMouseDown={onResizeStart} />
          {workspacePanel}
        </div>
      )}

      {workspaceOpen && layoutMode === 'overlay' && (
        <>
          <div className="assistant-workspace-backdrop" onClick={closeWorkspace} />
          <div className="assistant-workspace assistant-workspace--overlay">
            {workspacePanel}
          </div>
        </>
      )}

      {workspaceOpen && layoutMode === 'modal' && (
        <div className="overlay" onClick={closeWorkspace}>
          <div className="modal assistant-workspace--modal" onClick={e => e.stopPropagation()}>
            {workspacePanel}
          </div>
        </div>
      )}
    </div>
  )
}
