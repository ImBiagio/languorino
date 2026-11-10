// Client HTTP: l'access token vive in memoria (mai in localStorage), il refresh
// e' un cookie httpOnly gestito dal browser. Su 401 si tenta un refresh e si
// riprova la richiesta una sola volta.

// In sviluppo l'API sta su un'altra porta (VITE_API_BASE_URL); in produzione
// frontend e API escono dallo stesso dominio, quindi basta l'origin della pagina.
import { gettext, interpolate } from './i18n'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || window.location.origin

/** URL completo di un file di `/media/...` (in sviluppo sta sulla porta dell'API). */
export function mediaUrl(path: string): string {
  return path.startsWith('http') ? path : `${BASE_URL}${path}`
}

let accessToken: string | null = null
let onUnauthenticated: (() => void) | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function getAccessToken() {
  return accessToken
}

export function setUnauthenticatedHandler(handler: (() => void) | null) {
  onUnauthenticated = handler
}

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(status: number, data: unknown) {
    super(extractMessage(data) ?? interpolate(gettext('Errore %s'), [status]))
    this.status = status
    this.data = data
  }

  /** Errori per campo, per attaccarli agli input del form. */
  fieldErrors(): Record<string, string> {
    if (!this.data || typeof this.data !== 'object') return {}
    const out: Record<string, string> = {}
    for (const [key, value] of Object.entries(this.data as Record<string, unknown>)) {
      out[key] = Array.isArray(value) ? String(value[0]) : String(value)
    }
    return out
  }
}

function extractMessage(data: unknown): string | null {
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>
    if (typeof record.detail === 'string') return record.detail
    const first = Object.values(record)[0]
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string') return first
  }
  return null
}

interface RequestOptions {
  method?: string
  body?: unknown
  params?: Record<string, string | number | undefined | null>
  skipRefresh?: boolean
  /** Risposta binaria (es. un file protetto) invece di JSON. */
  blob?: boolean
}

function buildUrl(path: string, params?: RequestOptions['params']) {
  const url = new URL(path.startsWith('http') ? path : `${BASE_URL}${path}`)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value))
      }
    }
  }
  return url.toString()
}

// Un solo refresh in volo: il doppio effetto di StrictMode all'avvio e le
// query che prendono 401 insieme (access scaduto) aspettano la stessa risposta
// invece di ruotare il cookie una volta a testa.
let refreshing: Promise<boolean> | null = null

async function doRefresh(): Promise<boolean> {
  const response = await fetch(buildUrl('/api/auth/refresh'), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) return false
  const data = (await response.json()) as { access: string }
  accessToken = data.access
  return true
}

function refreshAccessToken(): Promise<boolean> {
  refreshing ??= doRefresh().finally(() => {
    refreshing = null
  })
  return refreshing
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, params, skipRefresh, blob } = options
  // Un FormData (upload di file) va lasciato al browser: e' lui a mettere il
  // Content-Type multipart col suo boundary.
  const isForm = body instanceof FormData
  const headers: Record<string, string> = isForm ? {} : { 'Content-Type': 'application/json' }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`

  const response = await fetch(buildUrl(path, params), {
    method,
    credentials: 'include',
    headers,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })

  if (response.status === 401 && !skipRefresh) {
    const refreshed = await refreshAccessToken()
    if (refreshed) return request<T>(path, { ...options, skipRefresh: true })
    onUnauthenticated?.()
  }

  if (response.status === 204) return undefined as T
  if (blob && response.ok) return (await response.blob()) as T

  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, payload)
  return payload as T
}

export const api = {
  get: <T>(path: string, params?: RequestOptions['params']) => request<T>(path, { params }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
  delete: <T>(path: string, body?: unknown) => request<T>(path, { method: 'DELETE', body }),
  // Un <img src> non manda l'header Authorization: i file protetti si scaricano qui.
  blob: (path: string) => request<Blob>(path, { blob: true }),
  refresh: refreshAccessToken,
}
