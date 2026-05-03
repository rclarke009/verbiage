/**
 * Calls the FastAPI backend. Sends Bearer token from Supabase when set via setAuthTokenGetter.
 * Use `anonymous: true` for /config and POST /auth/signup.
 */

export function apiOrigin(): string {
  const o = import.meta.env.VITE_API_ORIGIN ?? ''
  return typeof o === 'string' ? o.trim() : ''
}

type TokenGetter = () => Promise<string | null>

let authTokenGetter: TokenGetter | null = null

export function setAuthTokenGetter(fn: TokenGetter | null) {
  authTokenGetter = fn
}

function joinUrl(origin: string, path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  if (!origin) return p
  return `${origin.replace(/\/$/, '')}${p}`
}

export async function getAuthFetchInit(init: RequestInit = {}): Promise<RequestInit> {
  const headers = new Headers(init.headers)
  if (authTokenGetter) {
    const token = await authTokenGetter()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }
  const out: RequestInit = { ...init, headers }
  return out
}

export async function apiFetch(
  path: string,
  init: RequestInit & { anonymous?: boolean } = {},
): Promise<Response> {
  const { anonymous, ...rest } = init
  const url = joinUrl(apiOrigin(), path)
  const headers = new Headers(rest.headers)
  let body = rest.body
  if (!(body instanceof FormData) && body !== undefined && !headers.has('Content-Type')) {
    if (typeof body === 'string') headers.set('Content-Type', 'application/json')
  }
  if (!anonymous && authTokenGetter) {
    const token = await authTokenGetter()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }
  return fetch(url, { ...rest, headers })
}

export async function readErrorDetail(res: Response): Promise<string> {
  try {
    const t = await res.text()
    if (!t) return res.statusText || `HTTP ${res.status}`
    try {
      const j = JSON.parse(t) as { detail?: string | unknown }
      if (j && typeof j.detail === 'string') return j.detail
    } catch {
      /* not JSON */
    }
    return t.slice(0, 500)
  } catch {
    return res.statusText || `HTTP ${res.status}`
  }
}
