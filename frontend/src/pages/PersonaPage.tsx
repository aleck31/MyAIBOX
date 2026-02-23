import { usePersonaSession } from '../hooks/usePersonaSession'
import PersonaChat from '../components/PersonaChat'

export default function PersonaPage() {
  const { config, prefs, loading, error } = usePersonaSession()

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
          <p style={{ fontWeight: 600 }}>Failed to load session</p>
          <p style={{ fontSize: '13px', marginTop: '8px' }}>{error}</p>
        </div>
      </div>
    )
  }

  if (!config || !prefs) return null

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <PersonaChat config={config} initialPrefs={prefs} />
    </div>
  )
}
