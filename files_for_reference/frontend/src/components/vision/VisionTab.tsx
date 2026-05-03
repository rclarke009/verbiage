import { useRef, useState } from 'react'
import { analyzePhoto } from '../../api/vision'
import type { RagGroundedVisionResponse, Source, VisionResponse } from '../../types'

const CLASSIFICATION_LABELS: Record<string, [string, string]> = {
  hail_damage:   ['🧊 Hail Damage',   '#1976D2'],
  wear_and_tear: ['🕰️ Wear & Tear',   '#388e3c'],
  storm_damage:  ['🌩️ Storm Damage',  '#1976D2'],
  impact_damage: ['💥 Impact Damage', '#1976D2'],
  no_damage:     ['✅ No Damage',      '#388e3c'],
  other:         ['❓ Other',          '#757575'],
  unknown:       ['❓ Unknown',        '#757575'],
}

const CONFIDENCE_COLORS: Record<string, string> = {
  high: '#388e3c', medium: '#1976D2', low: '#757575',
}

function VisualAnalysisPanel({ result }: { result: VisionResponse }) {
  const [label, color] = CLASSIFICATION_LABELS[result.classification] ?? ['❓ Unknown', '#757575']
  const confColor = CONFIDENCE_COLORS[result.confidence] ?? '#757575'

  return (
    <div>
      <div style={{ fontSize: 18, fontWeight: 700, color, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13, color: confColor, marginBottom: 10 }}>
        Confidence: <strong>{result.confidence}</strong>
      </div>
      {result.findings.length > 0 && (
        <>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Findings:</div>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
            {result.findings.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </>
      )}
      {result.recommendation && (
        <p style={{ fontSize: 13, marginTop: 10 }}>
          <strong>Recommended action:</strong> {result.recommendation}
        </p>
      )}
      {result.notes && <p style={{ fontSize: 12, color: '#888', marginTop: 6 }}>Note: {result.notes}</p>}
      {result.classification === 'unknown' && result.raw && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ fontSize: 12, cursor: 'pointer', color: '#888' }}>Full Claude response</summary>
          <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', marginTop: 8 }}>{result.raw}</pre>
        </details>
      )}
    </div>
  )
}

function SourcesPanel({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null
  return (
    <details style={{ marginTop: 10 }}>
      <summary style={{ fontSize: 12, cursor: 'pointer', color: '#1976D2', fontWeight: 600 }}>
        Sources ({sources.length})
      </summary>
      <div style={{ marginTop: 8 }}>
        {sources.map((src, i) => (
          <div key={i} style={{ fontSize: 12, color: '#555', padding: '4px 0', borderTop: i > 0 ? '1px solid #eee' : 'none' }}>
            📄 <strong>{src.filename}</strong>
            {src.page ? ` — Page ${src.page}` : ''}
            {src.section ? ` · ${src.section}` : ''}
            {src.source_url && src.source_type === 'google_drive' && (
              <> · <a href={src.source_url} target="_blank" rel="noreferrer" style={{ color: '#1976D2' }}>Open in Drive</a></>
            )}
          </div>
        ))}
      </div>
    </details>
  )
}

function RagPanel({ result }: { result: RagGroundedVisionResponse }) {
  if (result.skipped) {
    return (
      <div style={{ fontSize: 13, color: '#555', background: '#f5f5f5', borderRadius: 6, padding: '10px 14px' }}>
        ℹ️ {result.skip_reason || 'No documents ingested yet.'}
      </div>
    )
  }
  return (
    <div>
      <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{result.rag_answer}</div>
      <SourcesPanel sources={result.sources} />
    </div>
  )
}

function CombinedResult({ combined }: { combined: RagGroundedVisionResponse }) {
  return (
    <div style={{ background: '#f9f9f9', borderRadius: 8, padding: '16px 20px', marginTop: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 14, color: '#1976D2', marginBottom: 10, paddingBottom: 6, borderBottom: '1px solid #e0e0e0' }}>
        Document-Grounded Interpretation
      </div>
      <RagPanel result={combined} />

      <div style={{ borderTop: '1px solid #e0e0e0', margin: '14px 0' }} />

      <div style={{ fontWeight: 700, fontSize: 14, color: '#1976D2', marginBottom: 10 }}>
        Visual Analysis (Context-Free)
      </div>
      <VisualAnalysisPanel result={combined.vision_result} />
    </div>
  )
}

export function VisionTab() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [context, setContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState<Array<{ filename: string; combined: RagGroundedVisionResponse }>>([])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setSelectedFile(file)
    setPreview(URL.createObjectURL(file))
    setError('')
    e.target.value = ''
  }

  const analyze = async () => {
    if (!selectedFile) return
    setLoading(true)
    setError('')
    try {
      const combined = await analyzePhoto(selectedFile, context)
      setHistory(prev => [{ filename: selectedFile.name, combined }, ...prev])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 style={{ marginTop: 0, color: '#1976D2', fontSize: 18 }}>🔍 Photo Analysis</h2>

      <div
        onClick={() => inputRef.current?.click()}
        style={{
          border: '2px dashed #90CAF9', borderRadius: 8, padding: '20px', textAlign: 'center',
          cursor: 'pointer', background: '#F3F9FF', marginBottom: 12,
        }}
      >
        {preview
          ? <img src={preview} alt="preview" style={{ maxHeight: 200, maxWidth: '100%', borderRadius: 6 }} />
          : <span style={{ color: '#555', fontSize: 13 }}>Click to upload a job site photo (JPG, PNG, WebP)</span>
        }
      </div>
      <input ref={inputRef} type="file" accept=".jpg,.jpeg,.png,.webp" onChange={handleFileChange} style={{ display: 'none' }} />

      <input
        value={context}
        onChange={e => setContext(e.target.value)}
        placeholder="Optional context (e.g. 'roof on a 2019 house in Texas')"
        style={{
          width: '100%', boxSizing: 'border-box', marginBottom: 10,
          border: '1px solid #ccc', borderRadius: 6, padding: '7px 12px', fontSize: 13,
        }}
      />

      <button
        onClick={analyze}
        disabled={!selectedFile || loading}
        style={{
          background: '#1976D2', color: '#fff', border: 'none', borderRadius: 6,
          padding: '9px 20px', cursor: 'pointer', fontSize: 14, fontWeight: 600,
          opacity: !selectedFile || loading ? 0.5 : 1, marginBottom: 8,
        }}
      >
        {loading ? 'Analyzing…' : 'Analyze Photo'}
      </button>

      {error && (
        <div style={{ color: '#c62828', background: '#FFEBEE', borderRadius: 6, padding: '8px 12px', fontSize: 13, marginBottom: 12 }}>
          ✗ {error}
        </div>
      )}

      {history.length > 0 && <CombinedResult combined={history[0].combined} />}

      {history.length > 1 && (
        <details style={{ marginTop: 20 }}>
          <summary style={{ cursor: 'pointer', fontSize: 13, color: '#1976D2', fontWeight: 600 }}>
            Previous analyses ({history.length - 1})
          </summary>
          {history.slice(1).map((item, i) => (
            <div key={i} style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>{item.filename}</div>
              <CombinedResult combined={item.combined} />
            </div>
          ))}
        </details>
      )}
    </div>
  )
}
