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
  public_app_url: string
}

interface AuthCtx {
  loading: boolean
  error: string
  session: Session | null
  publicConfig: PublicAppConfig | null
  supabase: SupabaseClient | null
  passwordRecovery: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUpServer: (
    email: string,
    password: string,
    inviteCode?: string,
  ) => Promise<void>
  signOut: () => Promise<void>
  requestPasswordReset: (email: string) => Promise<void>
  completePasswordReset: (newPassword: string) => Promise<void>
}

const Ctx = createContext<AuthCtx | null>(null)

async function fetchPublicConfig(): Promise<PublicAppConfig> {
  const res = await apiFetch('/config', { anonymous: true })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const raw = (await res.json()) as Record<string, unknown>
  return {
    supabase_url: String(raw.supabase_url ?? ''),
    supabase_anon_key: String(raw.supabase_anon_key ?? ''),
    signup_invite_enabled: Boolean(raw.signup_invite_enabled),
    public_app_url: String(raw.public_app_url ?? ''),
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [publicConfig, setPublicConfig] = useState<PublicAppConfig | null>(null)
  const [supabase, setSupabase] = useState<SupabaseClient | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [passwordRecovery, setPasswordRecovery] = useState(false)

  useEffect(() => {
    let cancelled = false
    let unsubscribe: (() => void) | null = null
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

        const recoveryUrlHint =
          typeof window !== 'undefined' &&
          (window.location.hash.replace(/^#/, '').includes('type=recovery') ||
            window.location.search.includes('type=recovery'))

        const client = createClient(cfg.supabase_url, cfg.supabase_anon_key)
        setSupabase(client)

        const {
          data: { subscription },
        } = client.auth.onAuthStateChange((event, sess) => {
          if (cancelled) return
          if (event === 'PASSWORD_RECOVERY') {
            setPasswordRecovery(true)
          } else if (
            recoveryUrlHint &&
            sess &&
            (event === 'SIGNED_IN' || event === 'INITIAL_SESSION')
          ) {
            setPasswordRecovery(true)
          }
          setSession(sess ?? null)
        })
        unsubscribe = () => subscription.unsubscribe()

        const { data } = await client.auth.getSession()
        if (cancelled) return
        const sess = data.session ?? null
        setSession(sess)
        if (sess && recoveryUrlHint) setPasswordRecovery(true)
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : 'Failed to load /config')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
      unsubscribe?.()
    }
  }, [])

  useEffect(() => {
    setAuthTokenGetter(
      supabase ? async () => (await supabase.auth.getSession()).data.session?.access_token ?? null : null,
    )
    return () => setAuthTokenGetter(null)
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
    setPasswordRecovery(false)
    await supabase.auth.signOut()
  }, [supabase])

  const requestPasswordReset = useCallback(
    async (email: string) => {
      if (!supabase) throw new Error('Auth client not ready')
      const trimmed = email.trim()
      const base =
        publicConfig?.public_app_url && publicConfig.public_app_url.length > 0
          ? `${publicConfig.public_app_url.replace(/\/$/, '')}/`
          : `${typeof window !== 'undefined' ? window.location.origin : ''}/`
      const { error: err } = await supabase.auth.resetPasswordForEmail(trimmed, {
        redirectTo: base,
      })
      if (err) throw new Error(err.message)
    },
    [supabase, publicConfig],
  )

  const completePasswordReset = useCallback(
    async (newPassword: string) => {
      if (!supabase) throw new Error('Auth client not ready')
      const { error: err } = await supabase.auth.updateUser({ password: newPassword })
      if (err) throw new Error(err.message)
      setPasswordRecovery(false)
    },
    [supabase],
  )

  const value = useMemo(
    (): AuthCtx => ({
      loading,
      error,
      session,
      publicConfig,
      supabase,
      passwordRecovery,
      signIn,
      signUpServer,
      signOut,
      requestPasswordReset,
      completePasswordReset,
    }),
    [
      loading,
      error,
      session,
      publicConfig,
      supabase,
      passwordRecovery,
      signIn,
      signUpServer,
      signOut,
      requestPasswordReset,
      completePasswordReset,
    ],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth must be inside AuthProvider')
  return v
}
