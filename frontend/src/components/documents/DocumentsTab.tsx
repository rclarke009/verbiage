import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  deleteDocument,
  listDocuments,
  summarizeDocuments,
} from '../../api/documents'
import type { DocumentsListResponse } from '../../types'
import { StatsBar } from './StatsBar'
import { DocumentTable } from './DocumentTable'
import { UploadDropzone } from './UploadDropzone'

function filterDocs(
  docs: DocumentsListResponse['documents'],
  q: string,
): DocumentsListResponse['documents'] {
  const needle = q.trim().toLowerCase()
  if (!needle) return docs
  return docs.filter(
    d =>
      d.doc_id.toLowerCase().includes(needle)
      || (d.title ?? '').toLowerCase().includes(needle)
      || (d.snippet ?? '').toLowerCase().includes(needle),
  )
}

export function DocumentsTab() {
  const [search, setSearch] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data, isLoading: docsLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: listDocuments,
  })

  const rows = data?.documents ?? []
  const filtered = useMemo(() => filterDocs(rows, search), [rows, search])
  const stats = useMemo(() => summarizeDocuments(rows), [rows])

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => deleteDocument(docId),
    onMutate: docId => setDeleting(docId),
    onSettled: () => {
      setDeleting(null)
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })

  return (
    <div>
      <h2 style={{ marginTop: 0, color: '#0969da', fontSize: 18 }}>
        Document index
      </h2>

      <StatsBar stats={stats} />

      <UploadDropzone
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['documents'] })
        }}
      />

      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Filter by title, id, or snippet…"
        style={{
          width: '100%',
          boxSizing: 'border-box',
          marginBottom: 12,
          border: '1px solid #d0d7de',
          borderRadius: 6,
          padding: '7px 12px',
          fontSize: 13,
        }}
      />

      {docsLoading ? (
        <p style={{ color: '#888', fontSize: 13 }}>Loading…</p>
      ) : (
        <DocumentTable
          documents={filtered}
          onDelete={id => deleteMutation.mutate(id)}
          deleting={deleting}
        />
      )}
    </div>
  )
}
