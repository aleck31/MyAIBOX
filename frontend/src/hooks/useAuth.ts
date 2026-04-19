import { useState, useEffect } from 'react'
import { getMe } from '../api/client'

export interface AuthState {
  sub: string | null
  username: string | null
  email: string | null
  loading: boolean
}

export function useAuth(): AuthState {
  const [state, setState] = useState<Omit<AuthState, 'loading'>>({ sub: null, username: null, email: null })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getMe()
      .then((data) => {
        if (cancelled) return
        setState({
          sub: data?.sub ?? null,
          username: data?.username ?? null,
          email: data?.email ?? null,
        })
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setState({ sub: null, username: null, email: null })
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  return { ...state, loading }
}
