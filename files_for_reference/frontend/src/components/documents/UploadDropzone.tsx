import { useRef, useState } from 'react'
import { uploadDocument } from '../../api/documents'
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
      const r = await uploadDocument(file)
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
        onClick={() => inputRef.current?.click()}
        style={{
          border: '2px dashed #90CAF9', borderRadius: 8, padding: '20px 24px',
          textAlign: 'center', cursor: 'pointer', background: '#F3F9FF',
          color: '#555', fontSize: 13,
        }}
      >
        {uploading ? 'Uploading…' : '+ Upload PDF or DOCX'}
      </div>
      <input ref={inputRef} type="file" accept=".pdf,.docx,.doc" onChange={handleChange} style={{ display: 'none' }} />

      {result && (
        <div style={{ marginTop: 8, color: '#2e7d32', fontSize: 13, background: '#E8F5E9', borderRadius: 6, padding: '8px 12px' }}>
          {result.skipped
            ? `⏭ ${result.filename} already up to date — skipped`
            : `✓ Ingested ${result.filename}: ${result.chunks} chunks across ${result.pages} pages${result.ocr_used ? ' (OCR)' : ''}`}
        </div>
      )}
      {error && (
        <div style={{ marginTop: 8, color: '#c62828', fontSize: 13, background: '#FFEBEE', borderRadius: 6, padding: '8px 12px' }}>
          ✗ {error}
        </div>
      )}
    </div>
  )
}
