import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import LoginPage from './pages/LoginPage'
import AppLayout from './components/AppLayout'
import PersonaPage from './pages/PersonaPage'
import TextPage from './pages/TextPage'
import SummaryPage from './pages/SummaryPage'
import AskingPage from './pages/AskingPage'
import VisionPage from './pages/VisionPage'
import DrawPage from './pages/DrawPage'
import SettingsPage from './pages/SettingsPage'
import ModelsPage from './pages/ModelsPage'
import McpPage from './pages/McpPage'
import AssistantPage from './pages/AssistantPage'
import GradioPage from './pages/GradioPage'

function AuthGuard({ children }: { children: (username: string) => React.ReactNode }) {
  const { username, loading } = useAuth()

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

  if (!username) {
    return <Navigate to="/login" replace />
  }

  return <>{children(username)}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected — requires auth */}
        <Route
          path="/"
          element={
            <AuthGuard>
              {(username) => <AppLayout username={username} />}
            </AuthGuard>
          }
        >
          {/* Default: redirect to persona */}
          <Route index element={<Navigate to="/assistant" replace />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="persona" element={<PersonaPage />} />
          <Route path="text" element={<TextPage />} />
          <Route path="summary" element={<SummaryPage />} />
          <Route path="asking" element={<AskingPage />} />
          <Route path="vision" element={<VisionPage />} />
          <Route path="draw" element={<DrawPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="mcp" element={<McpPage />} />
          <Route path="legacy" element={<GradioPage />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
