import { useState, useEffect } from 'react'
import { getMe } from '../api/client'

export interface AuthState {
  username: string | null
  loading: boolean
}

export function useAuth(): AuthState {
  const [username, setUsername] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getMe()
      .then((data) => {
        if (!cancelled) {
          setUsername(data?.username ?? null)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUsername(null)
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  return { username, loading }
}
