import { useState, useEffect, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { loginApi } from '../api/client'

const REMEMBERED_USER_KEY = 'aibox_remembered_user'
const PBKDF2_SALT = new TextEncoder().encode('my-aibox')
const PBKDF2_ITERATIONS = 10000

async function deriveKey(username: string) {
  const raw = await crypto.subtle.importKey('raw', new TextEncoder().encode(username), 'PBKDF2', false, ['deriveKey'])
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: PBKDF2_SALT, iterations: PBKDF2_ITERATIONS, hash: 'SHA-256' },
    raw, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']
  )
}

async function encryptAndSave(username: string, password: string) {
  const key = await deriveKey(username)
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const encrypted = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, new TextEncoder().encode(password)))
  // Pack: 1 byte username length + username + 12 bytes IV + ciphertext
  const uBytes = new TextEncoder().encode(username)
  const packed = new Uint8Array(1 + uBytes.length + 12 + encrypted.length)
  packed[0] = uBytes.length
  packed.set(uBytes, 1)
  packed.set(iv, 1 + uBytes.length)
  packed.set(encrypted, 1 + uBytes.length + 12)
  localStorage.setItem(REMEMBERED_USER_KEY, btoa(String.fromCharCode(...packed)))
}

async function loadSaved(): Promise<{ u: string; p: string } | null> {
  const saved = localStorage.getItem(REMEMBERED_USER_KEY)
  if (!saved) return null
  try {
    const packed = Uint8Array.from(atob(saved), c => c.charCodeAt(0))
    const uLen = packed[0]
    const uBytes = packed.slice(1, 1 + uLen)
    const iv = packed.slice(1 + uLen, 1 + uLen + 12)
    const encrypted = packed.slice(1 + uLen + 12)
    const username = new TextDecoder().decode(uBytes)
    const key = await deriveKey(username)
    const decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, encrypted)
    return { u: username, p: new TextDecoder().decode(decrypted) }
  } catch {
    localStorage.removeItem(REMEMBERED_USER_KEY)
    return null
  }
}

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    loadSaved().then(result => {
      if (result) {
        setUsername(result.u)
        setPassword(result.p)
        setRemember(true)
      }
    })
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
          await encryptAndSave(username.trim(), password)
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
        <div className="login-panel-footer">© iX · v{__APP_VERSION__}</div>
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
