import { useReportSearch } from '../../hooks/useReportSearch'
import { useCollectedPassages } from '../../hooks/useCollectedPassages'
import { ResultCard } from './ResultCard'
import { CollectedPanel } from './CollectedPanel'
import { ChatInput } from './ChatInput'

export function ChatTab() {
  const { results, searching, search, removeResult, clearResults } = useReportSearch()
  const { passages, savePassage, removePassage, clearPassages } = useCollectedPassages()

  return (
    <div style={{ display: 'flex', gap: 20, height: 'calc(100vh - 140px)' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <ChatInput onSubmit={search} disabled={searching} />

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
                <ResultCard key={r.id} result={r} onSave={savePassage} onRemove={removeResult} />
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
