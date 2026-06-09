import { useState, type KeyboardEvent } from 'react'

interface Props {
  onSubmit: (question: string) => void
  disabled: boolean
  placeholder?: string
  buttonLabel?: string
}

export function ChatInput({
  onSubmit,
  disabled,
  placeholder = 'Search past reports for a damage type… (Enter to search)',
  buttonLabel = 'Search',
}: Props) {
  const [value, setValue] = useState('')

  const submit = () => {
    const q = value.trim()
    if (!q || disabled) return
    onSubmit(q)
    setValue('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', padding: '12px 0' }}>
      <textarea
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={2}
        style={{
          flex: 1, resize: 'none', borderRadius: 8, border: '1px solid var(--app-border)',
          padding: '8px 12px', fontSize: 14, fontFamily: 'inherit',
          outline: 'none',
        }}
      />
      <button
        onClick={submit}
        disabled={disabled || !value.trim()}
        style={{
          background: 'var(--app-primary)', color: 'var(--app-on-primary)', border: 'none', borderRadius: 8,
          padding: '10px 18px', cursor: 'pointer', fontSize: 14, fontWeight: 600,
          opacity: disabled || !value.trim() ? 0.5 : 1,
        }}
      >
        {disabled ? '…' : buttonLabel}
      </button>
    </div>
  )
}
