import { useEffect, useState } from 'react'
import { useReportSearch } from '../../hooks/useReportSearch'
import { useCollectedPassages } from '../../hooks/useCollectedPassages'
import { useAuth } from '../../context/AuthContext'
import { ResultCard } from './ResultCard'
import { CollectedPanel } from './CollectedPanel'
import { ChatInput } from './ChatInput'

const RETRIEVAL_DEBUG_STORAGE_KEY = 'verbiage-show-retrieval-debug'

function loadShowRetrievalDebug(): boolean {
  if (typeof window === 'undefined') return true
  try {
    const raw = window.localStorage.getItem(RETRIEVAL_DEBUG_STORAGE_KEY)
    if (raw === null) return true
    return raw === '1' || raw === 'true'
  } catch {
    return true
  }
}

export function ChatTab() {
  const { publicConfig, session } = useAuth()
  const guestDemo = !session && (!!publicConfig?.demo_mode || !!publicConfig?.demo_anonymous)
  const { results, searching, search, removeResult, clearResults } = useReportSearch(
    3,
    'auto',
    session?.user?.id ?? null,
  )
  const { passages, savePassage, removePassage, clearPassages } = useCollectedPassages(
    session?.user?.id ?? null,
  )
  const [showRetrievalDebug, setShowRetrievalDebug] = useState(loadShowRetrievalDebug)

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(
      RETRIEVAL_DEBUG_STORAGE_KEY,
      showRetrievalDebug ? '1' : '0',
    )
  }, [showRetrievalDebug])

  return (
    <div style={{ display: 'flex', gap: 20, height: 'calc(100vh - 140px)' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <ChatInput
          onSubmit={search}
          disabled={searching}
          placeholder={
            guestDemo
              ? 'Try: what causes shingle damage after hail? (Enter to search)'
              : undefined
          }
        />
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 12,
            color: 'var(--app-text-subtle)',
            marginBottom: 4,
            cursor: 'pointer',
            userSelect: 'none',
          }}
        >
          <input
            type="checkbox"
            checked={showRetrievalDebug}
            onChange={e => setShowRetrievalDebug(e.target.checked)}
          />
          Show retrieval retries (rewritten query)
        </label>

        {results.length === 0 ? (
          <div style={{ color: 'var(--app-text-subtle)', textAlign: 'center', marginTop: 40, fontSize: 14 }}>
            <p>Search past engineering reports for a damage type.</p>
            <p style={{ fontSize: 12 }}>
              Each search is independent and grounded in retrieved passages. Save the text you
              want to reuse to your collection on the right.
            </p>
          </div>
        ) : (
          <>
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4, marginTop: 4 }}>
              {results.map(r => (
                <ResultCard
                  key={r.id}
                  result={r}
                  onSave={savePassage}
                  onRemove={removeResult}
                  showRetrievalDebug={showRetrievalDebug}
                  canDownloadSources={!!session}
                />
              ))}
            </div>
            <button
              onClick={clearResults}
              style={{ alignSelf: 'flex-start', background: 'none', border: 'none', color: 'var(--app-text-subtle)', cursor: 'pointer', fontSize: 12, padding: '4px 0' }}
            >
              Clear results
            </button>
          </>
        )}
      </div>

      <CollectedPanel passages={passages} onRemove={removePassage} onClear={clearPassages} />
    </div>
  )
}
