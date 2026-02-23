import { useState, useEffect } from 'react'
import { getConfig, getSession } from '../api/client'
import type { PersonaConfig, PersonaPrefs } from '../types/persona'

interface UsePersonaSessionResult {
  config: PersonaConfig | null
  prefs: PersonaPrefs | null
  loading: boolean
  error: string | null
}

export function usePersonaSession(): UsePersonaSessionResult {
  const [config, setConfig] = useState<PersonaConfig | null>(null)
  const [prefs, setPrefs] = useState<PersonaPrefs | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [configData, sessionData] = await Promise.all([
          getConfig(),
          getSession(),
        ])
        if (!cancelled) {
          setConfig(configData)
          setPrefs(sessionData)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load session')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  return { config, prefs, loading, error }
}
