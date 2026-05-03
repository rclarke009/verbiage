interface Tab {
  id: string
  label: string
}

const TABS: Tab[] = [
  { id: 'chat', label: '💬 Ask a Question' },
  { id: 'documents', label: '📁 Document Index' },
  { id: 'drive', label: '☁️ Google Drive' },
  { id: 'vision', label: '🔍 Photo Analysis' },
]

interface Props {
  active: string
  onChange: (id: string) => void
}

export function TabBar({ active, onChange }: Props) {
  return (
    <nav style={{ display: 'flex', gap: 4, borderBottom: '2px solid #e0e0e0', marginBottom: 24 }}>
      {TABS.map(tab => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          style={{
            padding: '10px 18px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: 14,
            fontWeight: active === tab.id ? 700 : 400,
            color: active === tab.id ? '#1976D2' : '#555',
            borderBottom: active === tab.id ? '2px solid #1976D2' : '2px solid transparent',
            marginBottom: -2,
          }}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}
