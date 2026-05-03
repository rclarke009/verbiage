interface Tab {
  id: string
  label: string
}

interface Props {
  tabs: Tab[]
  active: string
  onChange: (id: string) => void
}

export function TabBar({ tabs, active, onChange }: Props) {
  return (
    <nav
      role="tablist"
      aria-label="Main"
      style={{ display: 'flex', gap: 4, borderBottom: '2px solid #d0d7de', marginBottom: 24, flexWrap: 'wrap' }}
    >
      {tabs.map(tab => (
        <button
          role="tab"
          type="button"
          key={tab.id}
          aria-selected={active === tab.id}
          onClick={() => onChange(tab.id)}
          style={{
            padding: '10px 16px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: 14,
            fontWeight: active === tab.id ? 700 : 400,
            color: active === tab.id ? '#0969da' : '#24292f',
            borderBottom: active === tab.id ? '2px solid #0969da' : '2px solid transparent',
            marginBottom: -2,
          }}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}
