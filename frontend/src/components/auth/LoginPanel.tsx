import { useState } from 'react'

import { useAuth } from '../../context/AuthContext'

const inp: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  marginTop: 4,
  padding: '8px 12px',
  borderRadius: 6,
  border: '1px solid #d0d7de',
  fontSize: 14,
}

export function LoginPanel() {
  const { loading, error: bootErr, session, signIn, signOut, signUpServer, publicConfig } =
    useAuth()
  const inviteEnabled = !!publicConfig?.signup_invite_enabled
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [invite, setInvite] = useState('')
  const [formErr, setFormErr] = useState('')
  const [pending, setPending] = useState(false)

  if (loading) {
    return <p style={{ color: '#57606a' }}>Connecting…</p>
  }

  if (bootErr) {
    return (
      <div
        role="alert"
        style={{
          background: '#FFEBEE',
          color: '#c62828',
          padding: 12,
          borderRadius: 8,
          fontSize: 14,
        }}
      >
        {bootErr}
      </div>
    )
  }

  if (session?.user?.email) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <span style={{ color: '#24292f', fontSize: 14 }}>{session.user.email}</span>
        <button
          type="button"
          onClick={() => signOut()}
          style={{
            padding: '6px 12px',
            borderRadius: 6,
            border: '1px solid #d0d7de',
            background: '#f6f8fa',
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Sign out
        </button>
      </div>
    )
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormErr('')
    setPending(true)
    try {
      if (mode === 'signup') {
        await signUpServer(email, password, inviteEnabled ? invite : undefined)
      } else {
        await signIn(email, password)
      }
    } catch (err) {
      setFormErr(err instanceof Error ? err.message : String(err))
    } finally {
      setPending(false)
    }
  }

  const tabBtn = (active: boolean): React.CSSProperties => ({
    padding: '8px 14px',
    borderRadius: 6,
    border: active ? '1px solid #0969da' : '1px solid #d0d7de',
    background: active ? '#0969da' : '#fff',
    color: active ? '#fff' : '#24292f',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: active ? 600 : 400,
  })

  return (
    <div style={{ maxWidth: 360 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button type="button" style={tabBtn(mode === 'signin')} onClick={() => setMode('signin')}>
          Sign in
        </button>
        <button type="button" style={tabBtn(mode === 'signup')} onClick={() => setMode('signup')}>
          Sign up
        </button>
      </div>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <label style={{ fontSize: 13, color: '#57606a' }}>
          Email
          <input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} style={inp} />
        </label>
        <label style={{ fontSize: 13, color: '#57606a' }}>
          Password
          <input
            type="password"
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            required
            minLength={6}
            value={password}
            onChange={e => setPassword(e.target.value)}
            style={inp}
          />
        </label>
        {mode === 'signup' && inviteEnabled && (
          <label style={{ fontSize: 13, color: '#57606a' }}>
            Invite code (required when enabled on server)
            <input
              type="password"
              autoComplete="off"
              value={invite}
              onChange={e => setInvite(e.target.value)}
              style={inp}
            />
          </label>
        )}
        <button
          type="submit"
          disabled={pending}
          style={{
            marginTop: 4,
            padding: '10px 14px',
            borderRadius: 6,
            border: 'none',
            background: '#0969da',
            color: '#fff',
            fontWeight: 600,
            cursor: pending ? 'default' : 'pointer',
            opacity: pending ? 0.65 : 1,
          }}
        >
          {pending ? '…' : mode === 'signup' ? 'Create account' : 'Sign in'}
        </button>
        {mode === 'signup' && (
          <p style={{ fontSize: 11, color: '#57606a', margin: '4px 0 0 0', lineHeight: 1.4 }}>
            Accounts are gated by invite code or allowlist on this server (
            {publicConfig?.signup_invite_enabled ? 'invite enforced' : 'allowlist unless invite configured'}).
          </p>
        )}
      </form>
      {formErr && (
        <div style={{ marginTop: 12, fontSize: 13, color: '#cf222e' }} role="alert">
          {formErr}
        </div>
      )}
    </div>
  )
}
