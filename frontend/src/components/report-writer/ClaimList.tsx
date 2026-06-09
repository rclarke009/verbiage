import type { Claim, ReportTypeDefinition } from '../../types'

export function ClaimList({
  claims,
  loading,
  activeId,
  reportTypes,
  onSelect,
  onCreate,
}: {
  claims: Claim[]
  loading?: boolean
  activeId: string | null
  reportTypes: ReportTypeDefinition[]
  onSelect: (id: string) => void
  onCreate: () => void
}) {
  const typeLabel = (id: string | undefined) =>
    reportTypes.find(t => t.id === id)?.label ?? (id ? id.replace(/_/g, ' ') : null)
  return (
    <div style={{ width: 220, flexShrink: 0 }}>
      <button
        type="button"
        onClick={onCreate}
        style={{
          width: '100%',
          marginBottom: 12,
          padding: '8px 12px',
          background: 'var(--app-primary)',
          color: 'var(--app-on-primary)',
          border: 'none',
          borderRadius: 6,
          cursor: 'pointer',
          fontSize: 13,
        }}
      >
        New claim
      </button>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {loading ? (
          <p style={{ color: 'var(--app-text-subtle)', fontSize: 13, margin: 0 }}>Loading reports…</p>
        ) : (
        claims.map(c => (
          <button
            key={c.claim_id}
            type="button"
            onClick={() => onSelect(c.claim_id)}
            style={{
              textAlign: 'left',
              padding: '8px 10px',
              borderRadius: 6,
              border: activeId === c.claim_id ? '2px solid var(--app-primary)' : '1px solid var(--app-border)',
              background: activeId === c.claim_id ? 'var(--app-info-bg)' : 'var(--app-bg)',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            <div style={{ fontWeight: 600 }}>{c.title || 'Untitled claim'}</div>
            {typeLabel(c.property_metadata?.report_type) ? (
              <div style={{ fontSize: 11, color: 'var(--app-primary)', marginTop: 2 }}>
                {typeLabel(c.property_metadata?.report_type)}
              </div>
            ) : null}
            {c.property_metadata?.address ? (
              <div style={{ fontSize: 11, color: 'var(--app-text-muted)', marginTop: 2 }}>
                {c.property_metadata.address}
              </div>
            ) : null}
            <div style={{ fontSize: 11, color: 'var(--app-text-muted)', marginTop: 2 }}>{c.status}</div>
          </button>
        ))
        )}
      </div>
    </div>
  )
}
