import { useAuth } from '../hooks/useAuth'
import SettingsPanel from '../components/SettingsPanel'

export default function ModulesPage() {
  const { username } = useAuth()
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <SettingsPanel username={username || ''} tab="modules" />
    </div>
  )
}
