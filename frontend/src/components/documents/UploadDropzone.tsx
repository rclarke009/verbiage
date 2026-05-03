import { useRef, useState } from 'react'
import { uploadDocumentPdf } from '../../api/documents'
import type { IngestResponse } from '../../types'

interface Props {
  onSuccess: () => void
}

export function UploadDropzone({ onSuccess }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [result, setResult] = useState<IngestResponse | null>(null)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)

  const upload = async (file: File) => {
    setUploading(true)
    setError('')
    setResult(null)
    try {
      const r = await uploadDocumentPdf(file)
      setResult(r)
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) upload(file)
    e.target.value = ''
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={ev => ev.key === 'Enter' && inputRef.current?.click()}
        style={{
          border: '2px dashed #90CAF9',
          borderRadius: 8,
          padding: '20px 24px',
          textAlign: 'center',
          cursor: 'pointer',
          background: '#F3F9FF',
          color: '#555',
          fontSize: 13,
        }}
      >
        {uploading ? 'Uploading…' : '+ Upload PDF (report)'}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleChange}
        style={{ display: 'none' }}
      />

      {result && (
        <div
          style={{
            marginTop: 8,
            color: '#1a7f37',
            fontSize: 13,
            background: '#dafbe1',
            borderRadius: 6,
            padding: '8px 12px',
          }}
        >
          ✓ Ingested <strong>{result.doc_id}</strong> · {result.num_chunks} chunks · model{' '}
          {result.embedding_model}
        </div>
      )}
      {error && (
        <div
          style={{
            marginTop: 8,
            color: '#cf222e',
            fontSize: 13,
            background: '#FFEBEE',
            borderRadius: 6,
            padding: '8px 12px',
          }}
        >
          ✗ {error}
        </div>
      )}
    </div>
  )
}
