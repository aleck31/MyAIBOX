import { useState, useEffect, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { loginApi } from '../api/client'

const REMEMBERED_USER_KEY = 'aibox_remembered_user'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const saved = localStorage.getItem(REMEMBERED_USER_KEY)
    if (saved) {
      try {
        const { u, p } = JSON.parse(atob(saved))
        setUsername(u)
        setPassword(p)
      } catch {
        setUsername(saved) // legacy: plain username
      }
      setRemember(true)
    }
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password) return
    setLoading(true)
    setError('')
    try {
      const data = await loginApi(username.trim(), password)
      if (data.success) {
        if (remember) {
          localStorage.setItem(REMEMBERED_USER_KEY, btoa(JSON.stringify({ u: username.trim(), p: password })))
        } else {
          localStorage.removeItem(REMEMBERED_USER_KEY)
        }
        navigate('/')
      } else {
        setError(data.error || 'Authentication failed')
      }
    } catch {
      setError('Network error — please try again')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-root">
      {/* Brand panel */}
      <div className="login-panel">
        <div>
          <div className="login-panel-logo">
            AI<em>Box</em>
          </div>
          <div className="login-panel-tagline">GenAI 百宝箱</div>
        </div>
        <div className="login-panel-footer">Enterprise Edition</div>
      </div>

      {/* Form area */}
      <div className="login-form-area">
        <div className="login-card">
          <div className="login-card-title">Sign in</div>
          <div className="login-card-sub">Enter your credentials to continue</div>

          <form className="login-form" onSubmit={handleSubmit}>
            <div className="login-field">
              <label className="login-label" htmlFor="username">
                Username
              </label>
              <input
                id="username"
                className="login-input"
                type="text"
                autoComplete="username"
                placeholder="Enter username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={loading}
                required
              />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="password">
                Password
              </label>
              <div className="login-password-wrapper">
                <input
                  id="password"
                  className="login-input"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  required
                />
                <button
                  type="button"
                  className="login-password-toggle"
                  onClick={() => setShowPassword(v => !v)}
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19M1 1l22 22" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  ) : (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" strokeLinecap="round" strokeLinejoin="round"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {error && <div className="login-error">{error}</div>}

            <div className="login-options">
              <label className="login-remember">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                Remember me
              </label>
              <a className="login-forgot" href="/forgot-password">
                Forgot password?
              </a>
            </div>

            <button
              className="login-submit"
              type="submit"
              disabled={loading || !username.trim() || !password}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
