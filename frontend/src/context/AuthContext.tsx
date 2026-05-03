import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import type { Session, SupabaseClient } from '@supabase/supabase-js'
import { createClient } from '@supabase/supabase-js'

import {
  apiFetch,
  readErrorDetail,
  setAuthTokenGetter,
} from '../lib/api'

export interface PublicAppConfig {
  supabase_url: string
  supabase_anon_key: string
  signup_invite_enabled: boolean
}

interface AuthCtx {
  loading: boolean
  error: string
  session: Session | null
  publicConfig: PublicAppConfig | null
  supabase: SupabaseClient | null
  signIn: (email: string, password: string) => Promise<void>
  signUpServer: (
    email: string,
    password: string,
    inviteCode?: string,
  ) => Promise<void>
  signOut: () => Promise<void>
}

const Ctx = createContext<AuthCtx | null>(null)

async function fetchPublicConfig(): Promise<PublicAppConfig> {
  const res = await apiFetch('/config', { anonymous: true })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<PublicAppConfig>
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [publicConfig, setPublicConfig] = useState<PublicAppConfig | null>(null)
  const [supabase, setSupabase] = useState<SupabaseClient | null>(null)
  const [session, setSession] = useState<Session | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const cfg = await fetchPublicConfig()
        if (cancelled) return
        if (!cfg.supabase_url || !cfg.supabase_anon_key) {
          setError(
            'Supabase Auth is not configured on the server (/config missing credentials). Set SUPABASE_URL and SUPABASE_ANON_KEY.',
          )
          setLoading(false)
          return
        }
        setPublicConfig(cfg)
        const client = createClient(cfg.supabase_url, cfg.supabase_anon_key)
        setSupabase(client)
        const { data } = await client.auth.getSession()
        if (!cancelled) setSession(data.session ?? null)
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : 'Failed to load /config')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    setAuthTokenGetter(
      supabase ? async () => (await supabase.auth.getSession()).data.session?.access_token ?? null : null,
    )
    return () => setAuthTokenGetter(null)
  }, [supabase])

  useEffect(() => {
    if (!supabase) return
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_evt, sess) => {
      setSession(sess)
    })
    return () => subscription.unsubscribe()
  }, [supabase])

  const signIn = useCallback(
    async (email: string, password: string) => {
      if (!supabase) throw new Error('Auth client not ready')
      const { error: err } = await supabase.auth.signInWithPassword({ email, password })
      if (err) throw new Error(err.message)
    },
    [supabase],
  )

  const signUpServer = useCallback(
    async (email: string, password: string, inviteCode?: string) => {
      const res = await apiFetch('/auth/signup', {
        anonymous: true,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          invite_code: inviteCode?.trim() || null,
        }),
      })
      if (!res.ok) throw new Error(await readErrorDetail(res))
      await signIn(email, password)
    },
    [signIn],
  )

  const signOut = useCallback(async () => {
    if (!supabase) return
    await supabase.auth.signOut()
  }, [supabase])

  const value = useMemo(
    (): AuthCtx => ({
      loading,
      error,
      session,
      publicConfig,
      supabase,
      signIn,
      signUpServer,
      signOut,
    }),
    [loading, error, session, publicConfig, supabase, signIn, signUpServer, signOut],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth must be inside AuthProvider')
  return v
}
