import { useState } from 'react'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import { logoutApi } from '../api/client'

interface NavModule {
  key: string
  label: string
  route: string
  icon: React.ReactNode
}

// SVG icon components — clean, 16×16
function IconChat() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M2 3a1 1 0 011-1h10a1 1 0 011 1v7a1 1 0 01-1 1H5l-3 2V3z" />
    </svg>
  )
}
function IconBot() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <rect x="3" y="5" width="10" height="8" rx="1.5" />
      <path d="M6 5V3.5a2 2 0 014 0V5" />
      <circle cx="6" cy="9" r="1" fill="currentColor" stroke="none" />
      <circle cx="10" cy="9" r="1" fill="currentColor" stroke="none" />
    </svg>
  )
}
function IconText() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M3 4h10M3 8h7M3 12h5" strokeLinecap="round" />
    </svg>
  )
}
function IconSummary() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <rect x="2" y="2" width="12" height="12" rx="1.5" />
      <path d="M5 6h6M5 9h4" strokeLinecap="round" />
    </svg>
  )
}
function IconVision() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" />
      <circle cx="8" cy="8" r="2" />
    </svg>
  )
}
function IconAsking() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <circle cx="8" cy="8" r="6" />
      <path d="M8 11v.5M8 5a2 2 0 010 4" strokeLinecap="round" />
    </svg>
  )
}
function IconCode() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M5 5l-3 3 3 3M11 5l3 3-3 3M9 3l-2 10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function IconDraw() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M2 13l4-4 2 2 5-6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="13" cy="4" r="1.5" />
    </svg>
  )
}
function IconSettings() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <circle cx="8" cy="8" r="2" />
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.3 3.3l1.4 1.4M11.3 11.3l1.4 1.4M3.3 12.7l1.4-1.4M11.3 4.7l1.4-1.4" strokeLinecap="round" />
    </svg>
  )
}
function IconModels() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <rect x="2" y="3" width="12" height="10" rx="1.5" />
      <path d="M5 7h6M5 10h3" strokeLinecap="round" />
    </svg>
  )
}
function IconMcp() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <circle cx="8" cy="8" r="3" />
      <path d="M8 2v3M8 11v3M2 8h3M11 8h3" strokeLinecap="round" />
    </svg>
  )
}
function IconLegacy() {
  return (
    <svg className="nav-item-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <rect x="2" y="3" width="12" height="10" rx="1" /><path d="M5 7h6M5 9.5h4" strokeLinecap="round" />
    </svg>
  )
}
function IconLogout() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M6 3H3a1 1 0 00-1 1v8a1 1 0 001 1h3M10 5l3 3-3 3M13 8H6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const MODULES: NavModule[] = [
  { key: 'assistant', label: 'Assistant',  route: '/assistant', icon: <IconBot /> },
  { key: 'persona',   label: 'Persona',    route: '/persona', icon: <IconChat /> },
  { key: 'text',      label: 'Text',       route: '/text', icon: <IconText /> },
  { key: 'summary',   label: 'Summary',    route: '/summary', icon: <IconSummary /> },
  { key: 'vision',    label: 'Vision',     route: '/vision', icon: <IconVision /> },
  { key: 'asking',    label: 'Asking',     route: '/asking', icon: <IconAsking /> },
  { key: 'draw',      label: 'Draw',       route: '/draw', icon: <IconDraw /> },
]

const SETTINGS: NavModule[] = [
  { key: 'settings', label: 'Settings', route: '/settings', icon: <IconSettings /> },
  { key: 'models', label: 'Models', route: '/models', icon: <IconModels /> },
  { key: 'mcp', label: 'MCP Server', route: '/mcp', icon: <IconMcp /> },
  // { key: 'legacy', label: 'Legacy UI', route: '/legacy', icon: <IconLegacy /> },
]

interface AppLayoutProps {
  username: string
}

export default function AppLayout({ username }: AppLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  async function handleLogout() {
    await logoutApi()
    navigate('/login')
  }

  function isActive(mod: NavModule) {
    return location.pathname.startsWith(mod.route)
  }

  function navigateTo(mod: NavModule) {
    navigate(mod.route)
    setSidebarOpen(false)
  }

  const avatarChar = username.charAt(0).toUpperCase()

  return (
    <div className="shell-root">
      {/* Mobile hamburger */}
      <button className="sidebar-toggle" onClick={() => setSidebarOpen(o => !o)} aria-label="Toggle menu">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 5h14M3 10h14M3 15h14" strokeLinecap="round" />
        </svg>
      </button>

      {/* Overlay */}
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      {/* ── Sidebar ── */}
      <aside className={`sidebar${sidebarOpen ? ' open' : ''}`}>
        {/* Brand */}
        <div className="sidebar-brand">
          <div className="sidebar-brand-name">
            AI<em>Box</em>
          </div>
          <div className="sidebar-brand-sub">GenAI 百宝箱</div>
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          <div className="sidebar-nav-section">
            <div className="sidebar-nav-label">Modules</div>
            {MODULES.map((mod) => (
              <button
                key={mod.key}
                className={`nav-item ${isActive(mod) ? 'active' : ''}`}
                onClick={() => navigateTo(mod)}
              >
                {mod.icon}
                {mod.label}
              </button>
            ))}
          </div>

          <div className="sidebar-nav-section" style={{ marginTop: '8px' }}>
            <div className="sidebar-nav-label">Settings</div>
            {SETTINGS.map((mod) => (
              <button
                key={mod.key}
                className={`nav-item ${isActive(mod) ? 'active' : ''}`}
                onClick={() => navigateTo(mod)}
              >
                {mod.icon}
                {mod.label}
              </button>
            ))}
          </div>
        </nav>

        {/* Footer — user info */}
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">{avatarChar}</div>
            <span className="sidebar-user-name">{username}</span>
            <button
              className="sidebar-logout"
              onClick={handleLogout}
              title="Sign out"
            >
              <IconLogout />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Content ── */}
      <main className="shell-content">
        <Outlet />
      </main>
    </div>
  )
}
