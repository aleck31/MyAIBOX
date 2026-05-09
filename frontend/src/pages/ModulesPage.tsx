import { useCallback, useEffect, useState } from 'react'
import { getModulesConfig, updateModuleConfig } from '../api/client'
import type { ModulesData, ModuleConfig } from '../types/settings'
import ModuleCard from '../components/ModuleCard'

export default function ModulesPage() {
  const [data, setData] = useState<ModulesData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await getModulesConfig())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load modules')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { reload() }, [reload])

  const handleSave = useCallback(async (name: string, patch: ModuleConfig) => {
    await updateModuleConfig(name, patch)
    const next = await getModulesConfig()
    setData(next)
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

  if (error || !data) {
    return (
      <div className="state-screen">
        <div style={{ color: '#e07070', textAlign: 'center' }}>
          <p style={{ fontWeight: 600 }}>Failed to load</p>
          <p style={{ fontSize: 13, marginTop: 8 }}>{error ?? 'Unknown error'}</p>
        </div>
      </div>
    )
  }

  const entries = Object.entries(data.modules)

  return (
    <div className="settings-panel">
      <div className="section-bar">
        <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>Module settings</span>
        <div className="section-actions">
          <span style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}>
            {entries.length} modules
          </span>
        </div>
      </div>
      <div className="settings-content">
        <div className="settings-section" style={{ gap: 10 }}>
          {entries.map(([name, cfg], idx) => (
            <ModuleCard
              key={name}
              name={name}
              config={cfg}
              defaultOpen={idx === 0}
              models={data.model_choices}
              availableTools={data.available_tools}
              onSave={(patch) => handleSave(name, patch)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
