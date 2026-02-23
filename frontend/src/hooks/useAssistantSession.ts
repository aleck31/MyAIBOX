import { useState, useEffect } from 'react'
import { getAssistantConfig, getAssistantSession } from '../api/client'
import type { AssistantConfig, AssistantPrefs } from '../types/assistant'

export function useAssistantSession() {
  const [config, setConfig] = useState<AssistantConfig | null>(null)
  const [prefs, setPrefs] = useState<AssistantPrefs | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [configData, sessionData] = await Promise.all([
          getAssistantConfig(),
          getAssistantSession(),
        ])
        if (!cancelled) {
          setConfig(configData)
          setPrefs(sessionData)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load session')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  return { config, prefs, loading, error }
}
