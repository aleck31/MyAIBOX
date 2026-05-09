import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense, useEffect } from 'react'
import { useAuth } from './hooks/useAuth'
import LoginPage from './pages/LoginPage'
import AppLayout from './components/AppLayout'
import { SSO_ENABLED, redirectToLogin } from './auth'

function lazyLoad(loader: () => Promise<{ default: React.ComponentType }>) {
  return lazy(() => loader().catch(() => {
    window.location.reload()
    return new Promise(() => {}) // never resolves, page is reloading
  }))
}

const ChatPage = lazyLoad(() => import('./pages/ChatPage'))
const TextPage = lazyLoad(() => import('./pages/TextPage'))
const SummaryPage = lazyLoad(() => import('./pages/SummaryPage'))
const AskingPage = lazyLoad(() => import('./pages/AskingPage'))
const VisionPage = lazyLoad(() => import('./pages/VisionPage'))
const DrawPage = lazyLoad(() => import('./pages/DrawPage'))
const SettingsPage = lazyLoad(() => import('./pages/SettingsPage'))
const ModulesPage = lazyLoad(() => import('./pages/ModulesPage'))
const ModelsPage = lazyLoad(() => import('./pages/ModelsPage'))
const McpPage = lazyLoad(() => import('./pages/McpPage'))

function AuthGuard({ children }: { children: (username: string) => React.ReactNode }) {
  const { username, loading } = useAuth()

  useEffect(() => {
    if (!loading && !username && SSO_ENABLED) {
      redirectToLogin()
    }
  }, [loading, username])

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
    // SSO: redirect handled by effect above; render nothing meanwhile.
    return SSO_ENABLED ? null : <Navigate to="/login" replace />
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
          {/* Default: redirect to the built-in assistant agent */}
          <Route index element={<Navigate to="/chat/assistant" replace />} />
          {/* Chat with agent — unified endpoint for all built-in agents */}
          <Route path="chat" element={<Navigate to="/chat/assistant" replace />} />
          <Route path="chat/:agentId" element={<Suspense><ChatPage /></Suspense>} />
          {/* Legacy aliases — redirect to the new /chat path */}
          <Route path="assistant" element={<Navigate to="/chat/assistant" replace />} />
          <Route path="persona" element={<Navigate to="/chat/assistant" replace />} />
          <Route path="text" element={<Suspense><TextPage /></Suspense>} />
          <Route path="summary" element={<Suspense><SummaryPage /></Suspense>} />
          <Route path="asking" element={<Suspense><AskingPage /></Suspense>} />
          <Route path="vision" element={<Suspense><VisionPage /></Suspense>} />
          <Route path="draw" element={<Suspense><DrawPage /></Suspense>} />
          <Route path="settings/session" element={<Suspense><SettingsPage /></Suspense>} />
          <Route path="settings/modules" element={<Suspense><ModulesPage /></Suspense>} />
          <Route path="settings/models" element={<Suspense><ModelsPage /></Suspense>} />
          <Route path="settings/mcp" element={<Suspense><McpPage /></Suspense>} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
