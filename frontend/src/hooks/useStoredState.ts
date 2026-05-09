import { useCallback, useState } from 'react'

/** useState backed by localStorage. Typed-JSON roundtrip; silent on quota errors. */
export function useStoredState<T>(key: string, initial: T): [T, (v: T | ((p: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw != null ? (JSON.parse(raw) as T) : initial
    } catch {
      return initial
    }
  })

  const update = useCallback((next: T | ((p: T) => T)) => {
    setValue(prev => {
      const resolved = typeof next === 'function' ? (next as (p: T) => T)(prev) : next
      try { localStorage.setItem(key, JSON.stringify(resolved)) } catch { /* quota */ }
      return resolved
    })
  }, [key])

  return [value, update]
}
