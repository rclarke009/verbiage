import { useTheme, type ThemePreference } from '../../context/ThemeContext'

const OPTIONS: { value: ThemePreference; label: string; description: string }[] = [
  {
    value: 'system',
    label: 'System',
    description: 'Follow your device or browser appearance setting.',
  },
  {
    value: 'light',
    label: 'Light',
    description: 'Always use the light theme.',
  },
  {
    value: 'dark',
    label: 'Dark',
    description: 'Always use the dark theme.',
  },
]

export function PreferencesTab() {
  const { preference, setPreference } = useTheme()

  return (
    <section style={{ textAlign: 'left' }}>
      <h2 style={{ fontSize: 18, fontWeight: 650, margin: '0 0 6px', color: 'var(--app-text)' }}>
        Preferences
      </h2>
      <p style={{ margin: '0 0 20px', fontSize: 14, color: 'var(--app-text-muted)' }}>
        Customize how TrueAI looks on your device.
      </p>

      <fieldset
        style={{
          margin: 0,
          padding: 0,
          border: 'none',
        }}
      >
        <legend
          style={{
            display: 'block',
            fontSize: 14,
            fontWeight: 600,
            color: 'var(--app-text)',
            marginBottom: 12,
          }}
        >
          Appearance
        </legend>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 420 }}>
          {OPTIONS.map(option => {
            const selected = preference === option.value
            return (
              <label
                key={option.value}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  padding: '12px 14px',
                  borderRadius: 8,
                  border: `1px solid ${selected ? 'var(--app-primary)' : 'var(--app-border)'}`,
                  background: selected ? 'var(--app-surface)' : 'var(--app-bg)',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="radio"
                  name="theme-preference"
                  value={option.value}
                  checked={selected}
                  onChange={() => setPreference(option.value)}
                  style={{ marginTop: 3 }}
                />
                <span>
                  <span
                    style={{
                      display: 'block',
                      fontSize: 14,
                      fontWeight: selected ? 600 : 500,
                      color: 'var(--app-text)',
                    }}
                  >
                    {option.label}
                  </span>
                  <span
                    style={{
                      display: 'block',
                      marginTop: 2,
                      fontSize: 13,
                      color: 'var(--app-text-muted)',
                      lineHeight: 1.4,
                    }}
                  >
                    {option.description}
                  </span>
                </span>
              </label>
            )
          })}
        </div>
      </fieldset>
    </section>
  )
}
