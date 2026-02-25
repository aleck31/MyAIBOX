import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { useAuth } from './hooks/useAuth'
import LoginPage from './pages/LoginPage'
import AppLayout from './components/AppLayout'

const AssistantPage = lazy(() => import('./pages/AssistantPage'))
const PersonaPage = lazy(() => import('./pages/PersonaPage'))
const TextPage = lazy(() => import('./pages/TextPage'))
const SummaryPage = lazy(() => import('./pages/SummaryPage'))
const AskingPage = lazy(() => import('./pages/AskingPage'))
const VisionPage = lazy(() => import('./pages/VisionPage'))
const DrawPage = lazy(() => import('./pages/DrawPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const ModelsPage = lazy(() => import('./pages/ModelsPage'))
const McpPage = lazy(() => import('./pages/McpPage'))

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
          {/* Default: redirect to assistant */}
          <Route index element={<Navigate to="/assistant" replace />} />
          <Route path="assistant" element={<Suspense><AssistantPage /></Suspense>} />
          <Route path="persona" element={<Suspense><PersonaPage /></Suspense>} />
          <Route path="text" element={<Suspense><TextPage /></Suspense>} />
          <Route path="summary" element={<Suspense><SummaryPage /></Suspense>} />
          <Route path="asking" element={<Suspense><AskingPage /></Suspense>} />
          <Route path="vision" element={<Suspense><VisionPage /></Suspense>} />
          <Route path="draw" element={<Suspense><DrawPage /></Suspense>} />
          <Route path="settings" element={<Suspense><SettingsPage /></Suspense>} />
          <Route path="models" element={<Suspense><ModelsPage /></Suspense>} />
          <Route path="mcp" element={<Suspense><McpPage /></Suspense>} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
