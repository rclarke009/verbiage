import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchDocuments, fetchStats, deleteDocument } from '../../api/documents'
import { StatsBar } from './StatsBar'
import { DocumentTable } from './DocumentTable'
import { UploadDropzone } from './UploadDropzone'

export function DocumentsTab() {
  const [search, setSearch] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: docs, isLoading: docsLoading } = useQuery({
    queryKey: ['documents', search],
    queryFn: () => fetchDocuments(search || undefined),
  })

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
  })

  const deleteMutation = useMutation({
    mutationFn: (fileId: string) => deleteDocument(fileId),
    onMutate: (fileId) => setDeleting(fileId),
    onSettled: () => {
      setDeleting(null)
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  return (
    <div>
      <h2 style={{ marginTop: 0, color: '#1976D2', fontSize: 18 }}>📁 Document Index</h2>

      {stats && <StatsBar stats={stats} />}

      <UploadDropzone onSuccess={() => {
        queryClient.invalidateQueries({ queryKey: ['documents'] })
        queryClient.invalidateQueries({ queryKey: ['stats'] })
      }} />

      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search by filename…"
        style={{
          width: '100%', boxSizing: 'border-box', marginBottom: 12,
          border: '1px solid #ccc', borderRadius: 6, padding: '7px 12px', fontSize: 13,
        }}
      />

      {docsLoading ? (
        <p style={{ color: '#888', fontSize: 13 }}>Loading…</p>
      ) : (
        <DocumentTable
          documents={docs?.documents ?? []}
          onDelete={(id) => deleteMutation.mutate(id)}
          deleting={deleting}
        />
      )}
    </div>
  )
}
