import type { DocumentSummary } from '../../types'

interface Props {
  documents: DocumentSummary[]
  onDelete: (docId: string) => void
  deleting: string | null
}

function sourceLabel(doc: DocumentSummary): string {
  const s = (doc.source || '').toLowerCase()
  if (s.includes('drive') || s.includes('google')) return 'Drive'
  if (doc.source) return 'Stored'
  return '—'
}

export function DocumentTable({ documents, onDelete, deleting }: Props) {
  if (!documents.length) {
    return <p style={{ color: '#888', fontSize: 14 }}>No documents in the index yet.</p>
  }

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
      <thead>
        <tr style={{ background: '#f6f8fa', textAlign: 'left' }}>
          {['Title / ID', 'Source', 'Chunks', 'Updated', ''].map(h => (
            <th
              key={h}
              style={{ padding: '8px 10px', borderBottom: '1px solid #d0d7de', fontWeight: 600 }}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {documents.map(doc => {
          const label = doc.title?.trim() || doc.doc_id
          const ts = doc.source_modified_at ?? doc.created_at
          return (
            <tr key={doc.doc_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
              <td style={{ padding: '8px 10px', maxWidth: 280 }}>
                <span>{label}</span>
                {doc.source_url && (
                  <a
                    href={doc.source_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ marginLeft: 8, fontSize: 11, color: '#0969da' }}
                  >
                    link
                  </a>
                )}
                <div style={{ fontSize: 11, color: '#57606a' }}>{doc.doc_id}</div>
              </td>
              <td style={{ padding: '8px 10px', color: '#555' }}>{sourceLabel(doc)}</td>
              <td style={{ padding: '8px 10px' }}>{doc.num_chunks}</td>
              <td style={{ padding: '8px 10px', color: '#57606a', fontSize: 11 }}>
                {typeof ts === 'number' ? new Date(ts * 1000).toLocaleDateString() : '—'}
              </td>
              <td style={{ padding: '8px 10px' }}>
                <button
                  type="button"
                  onClick={() => onDelete(doc.doc_id)}
                  disabled={deleting === doc.doc_id}
                  style={{
                    background: 'none',
                    border: '1px solid #cf222e',
                    color: '#cf222e',
                    borderRadius: 4,
                    padding: '2px 8px',
                    cursor: 'pointer',
                    fontSize: 11,
                    opacity: deleting === doc.doc_id ? 0.5 : 1,
                  }}
                >
                  {deleting === doc.doc_id ? '…' : 'Delete'}
                </button>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
