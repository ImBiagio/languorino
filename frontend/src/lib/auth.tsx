import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { api, getAccessToken, setAccessToken, setUnauthenticatedHandler } from './api'
import { getLanguage, setLanguage } from './i18n'
import type { User } from './types'

const API = (import.meta.env.VITE_API_BASE_URL as string) || window.location.origin

/** Il giro di login su cornhub (ADR 0021), con ritorno su ``next`` (percorso dell'app). */
export function loginUrl(next = '/'): string {
  return `${API}/api/auth/sso/start?next=${encodeURIComponent(next)}`
}

interface AuthState {
  user: User | null
  ready: boolean
  logout: () => Promise<void>
  setUser: (user: User) => void
}

const AuthContext = createContext<AuthState | null>(null)

/** La lingua dell'account (arriva da cornhub al login) vince su quella del browser. */
function syncLanguage(user: User): User {
  if (user.language && user.language !== getLanguage()) {
    void setLanguage(user.language, getAccessToken())
  }
  return user
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  const logout = useCallback(async () => {
    const result = await api
      .post<{ logout_url?: string }>('/api/auth/logout')
      .catch(() => undefined)
    setAccessToken(null)
    setUser(null)
    // cornhub chiede se uscire anche dall'account della suite.
    if (result?.logout_url) window.location.assign(result.logout_url)
  }, [])

  // Al primo caricamento si prova il refresh: se il cookie e' ancora valido la
  // sessione riparte senza passare da cornhub (e cosi' anche dopo il login).
  useEffect(() => {
    let cancelled = false
    setUnauthenticatedHandler(() => {
      setAccessToken(null)
      setUser(null)
    })
    api
      .refresh()
      .then(async (ok) => {
        if (!ok || cancelled) return
        const me = await api.get<User>('/api/me')
        if (!cancelled) setUser(syncLanguage(me))
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setReady(true)
      })
    return () => {
      cancelled = true
      setUnauthenticatedHandler(null)
    }
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, ready, setUser, logout }),
    [user, ready, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth va usato dentro AuthProvider')
  return context
}
