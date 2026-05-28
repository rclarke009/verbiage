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

const linkBtn: React.CSSProperties = {
  padding: 0,
  border: 'none',
  background: 'none',
  color: '#0969da',
  cursor: 'pointer',
  fontSize: 13,
  textDecoration: 'underline',
}

export function LoginPanel() {
  const {
    loading,
    error: bootErr,
    session,
    passwordRecovery,
    signIn,
    signOut,
    signUpServer,
    publicConfig,
    requestPasswordReset,
    completePasswordReset,
  } = useAuth()
  const inviteEnabled = !!publicConfig?.signup_invite_enabled
  const [mode, setMode] = useState<'signin' | 'signup' | 'forgot'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [invite, setInvite] = useState('')
  const [formErr, setFormErr] = useState('')
  const [pending, setPending] = useState(false)
  const [forgotSent, setForgotSent] = useState(false)

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

  if (session?.user?.email && passwordRecovery) {
    const submitNew = async (e: React.FormEvent) => {
      e.preventDefault()
      setFormErr('')
      if (newPassword !== confirmPassword) {
        setFormErr('Passwords do not match.')
        return
      }
      if (newPassword.length < 6) {
        setFormErr('Password must be at least 6 characters.')
        return
      }
      setPending(true)
      try {
        await completePasswordReset(newPassword)
        setNewPassword('')
        setConfirmPassword('')
      } catch (err) {
        setFormErr(err instanceof Error ? err.message : String(err))
      } finally {
        setPending(false)
      }
    }

    return (
      <div style={{ maxWidth: 360 }}>
        <form onSubmit={submitNew} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <label style={{ fontSize: 13, color: '#57606a' }}>
            New password
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={6}
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              style={inp}
            />
          </label>
          <label style={{ fontSize: 13, color: '#57606a' }}>
            Confirm password
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={6}
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              style={inp}
            />
          </label>
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
            {pending ? '…' : 'Update password'}
          </button>
        </form>
        {formErr && (
          <div style={{ marginTop: 12, fontSize: 13, color: '#cf222e' }} role="alert">
            {formErr}
          </div>
        )}
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
      } else if (mode === 'signin') {
        await signIn(email, password)
      } else {
        await requestPasswordReset(email)
        setForgotSent(true)
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

  if (mode === 'forgot') {
    return (
      <div style={{ maxWidth: 360 }}>
        <p style={{ fontSize: 14, color: '#24292f', margin: '0 0 12px 0' }}>Reset your password</p>
        {forgotSent ? (
          <p style={{ fontSize: 14, color: '#57606a', margin: 0, lineHeight: 1.5 }}>
            If an account exists for that email, we sent a link. Check your inbox and spam folder.
          </p>
        ) : (
          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ fontSize: 13, color: '#57606a' }}>
              Email
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                style={inp}
              />
            </label>
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
              {pending ? '…' : 'Send reset link'}
            </button>
          </form>
        )}
        <p style={{ marginTop: 14, marginBottom: 0 }}>
          <button
            type="button"
            style={linkBtn}
            onClick={() => {
              setMode('signin')
              setForgotSent(false)
              setFormErr('')
            }}
          >
            Back to sign in
          </button>
        </p>
        {formErr && (
          <div style={{ marginTop: 12, fontSize: 13, color: '#cf222e' }} role="alert">
            {formErr}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 360 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button
          type="button"
          style={tabBtn(mode === 'signin')}
          onClick={() => {
            setMode('signin')
            setFormErr('')
          }}
        >
          Sign in
        </button>
        <button
          type="button"
          style={tabBtn(mode === 'signup')}
          onClick={() => {
            setMode('signup')
            setFormErr('')
          }}
        >
          Sign up
        </button>
      </div>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <label style={{ fontSize: 13, color: '#57606a' }}>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
            style={inp}
          />
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
        {mode === 'signin' && (
          <p style={{ margin: 0, textAlign: 'right' as const }}>
            <button
              type="button"
              style={linkBtn}
              onClick={() => {
                setMode('forgot')
                setFormErr('')
                setForgotSent(false)
              }}
            >
              Forgot password?
            </button>
          </p>
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
