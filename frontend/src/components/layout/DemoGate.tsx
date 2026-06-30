interface Props {
  featureName: string
  messageTemplate: string
}

export function DemoGate({ featureName, messageTemplate }: Props) {
  const message = messageTemplate.replace('{feature}', featureName)

  return (
    <section
      style={{
        marginTop: 24,
        padding: '24px 20px',
        borderRadius: 8,
        border: '1px solid var(--app-border)',
        background: 'var(--app-surface)',
        maxWidth: 520,
      }}
    >
      <h2 style={{ fontSize: 18, fontWeight: 650, margin: '0 0 10px', color: 'var(--app-text)' }}>
        {featureName}
      </h2>
      <p style={{ margin: 0, fontSize: 14, color: 'var(--app-text-muted)', lineHeight: 1.5 }}>
        {message}
      </p>
    </section>
  )
}
