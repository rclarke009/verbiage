import type { DocumentItem } from '../../types'

interface Props {
  documents: DocumentItem[]
  onDelete: (fileId: string) => void
  deleting: string | null
}

export function DocumentTable({ documents, onDelete, deleting }: Props) {
  if (!documents.length) {
    return <p style={{ color: '#888', fontSize: 14 }}>No documents in the index yet.</p>
  }

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
      <thead>
        <tr style={{ background: '#f5f5f5', textAlign: 'left' }}>
          {['Filename', 'Source', 'Pages', 'Chunks', 'OCR', 'Ingested', ''].map(h => (
            <th key={h} style={{ padding: '8px 10px', borderBottom: '1px solid #e0e0e0', fontWeight: 600 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {documents.map(doc => (
          <tr key={doc.file_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
            <td style={{ padding: '8px 10px' }}>
              <span>📄 {doc.filename}</span>
              {doc.source_url && doc.source_type === 'google_drive' && (
                <a href={doc.source_url} target="_blank" rel="noreferrer"
                  style={{ marginLeft: 8, fontSize: 11, color: '#1976D2' }}>☁️</a>
              )}
            </td>
            <td style={{ padding: '8px 10px', color: '#555' }}>
              {doc.source_type === 'google_drive' ? '☁️ Drive' : '💾 Local'}
            </td>
            <td style={{ padding: '8px 10px' }}>{doc.pages}</td>
            <td style={{ padding: '8px 10px' }}>{doc.chunks}</td>
            <td style={{ padding: '8px 10px' }}>{doc.ocr_used ? '✓' : '—'}</td>
            <td style={{ padding: '8px 10px', color: '#888', fontSize: 11 }}>
              {doc.ingested_at ? new Date(doc.ingested_at).toLocaleDateString() : '—'}
            </td>
            <td style={{ padding: '8px 10px' }}>
              <button
                onClick={() => onDelete(doc.file_id)}
                disabled={deleting === doc.file_id}
                style={{
                  background: 'none', border: '1px solid #f44336', color: '#f44336',
                  borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11,
                  opacity: deleting === doc.file_id ? 0.5 : 1,
                }}
              >
                {deleting === doc.file_id ? '…' : 'Delete'}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
