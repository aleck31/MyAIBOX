import { useState, useRef, useCallback } from 'react'
import { updateAssistantModel, syncAssistantHistory, updateAssistantCloudSync } from '../api/client'
import { clearRuntimeCache } from '../hooks/useAGUIRuntime'
import ModelSelector from './ModelSelector'
import ChatWindow, { type ChatWindowHandle } from './ChatWindow'
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
  const chatRef = useRef<ChatWindowHandle>(null)

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

  const handleClear = useCallback(() => {
    clearRuntimeCache(initialPrefs.session_id)
    setChatHistory([])
    setChatKey(k => k + 1)
  }, [initialPrefs.session_id])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="module-options-bar">
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
        </div>
      </div>

      <ChatWindow
        key={chatKey}
        ref={chatRef}
        threadId={initialPrefs.session_id}
        initialHistory={chatHistory}
        url="/api/assistant/chat"
      />
    </div>
  )
}
