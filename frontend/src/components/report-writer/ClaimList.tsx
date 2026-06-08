import type { Claim } from '../../types'

export function ClaimList({
  claims,
  activeId,
  onSelect,
  onCreate,
}: {
  claims: Claim[]
  activeId: string | null
  onSelect: (id: string) => void
  onCreate: () => void
}) {
  return (
    <div style={{ width: 220, flexShrink: 0 }}>
      <button
        type="button"
        onClick={onCreate}
        style={{
          width: '100%',
          marginBottom: 12,
          padding: '8px 12px',
          background: '#0969da',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          cursor: 'pointer',
          fontSize: 13,
        }}
      >
        New claim
      </button>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {claims.map(c => (
          <button
            key={c.claim_id}
            type="button"
            onClick={() => onSelect(c.claim_id)}
            style={{
              textAlign: 'left',
              padding: '8px 10px',
              borderRadius: 6,
              border: activeId === c.claim_id ? '2px solid #0969da' : '1px solid #d0d7de',
              background: activeId === c.claim_id ? '#ddf4ff' : '#fff',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            <div style={{ fontWeight: 600 }}>{c.title || 'Untitled claim'}</div>
            <div style={{ fontSize: 11, color: '#57606a' }}>{c.status}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
