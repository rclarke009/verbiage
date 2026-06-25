import { useEffect, useId, useRef, useState } from 'react'

import { useAddressSuggest } from '../../hooks/useAddressSuggest'
import type { AddressSuggestion } from '../../types'

const inputStyle: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  padding: 8,
  borderRadius: 6,
  border: '1px solid var(--app-border)',
}

export function AddressAutocomplete({
  value,
  onChange,
  disabled,
  placeholder = '412 Gulfview Drive, Tampa, FL',
}: {
  value: string
  onChange: (address: string) => void
  disabled?: boolean
  placeholder?: string
}) {
  const listId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const blurTimerRef = useRef<number | null>(null)
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(-1)
  const { suggestions, status, error } = useAddressSuggest(value)

  const showList = open && !disabled && value.trim().length >= 3
  const loading = showList && status === 'loading'
  const hasSuggestions = suggestions.length > 0
  const activeHighlight =
    showList && highlight >= 0 && highlight < suggestions.length ? highlight : -1

  useEffect(() => {
    return () => {
      if (blurTimerRef.current !== null) {
        window.clearTimeout(blurTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!open) return
    const onDocMouseDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocMouseDown)
    return () => document.removeEventListener('mousedown', onDocMouseDown)
  }, [open])

  const selectSuggestion = (suggestion: AddressSuggestion) => {
    onChange(suggestion.address)
    setOpen(false)
    setHighlight(-1)
  }

  const clearBlurTimer = () => {
    if (blurTimerRef.current !== null) {
      window.clearTimeout(blurTimerRef.current)
      blurTimerRef.current = null
    }
  }

  const scheduleClose = () => {
    clearBlurTimer()
    blurTimerRef.current = window.setTimeout(() => setOpen(false), 150)
  }

  return (
    <div ref={rootRef} style={{ position: 'relative' }}>
      <input
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        style={inputStyle}
        role="combobox"
        aria-expanded={showList}
        aria-controls={showList ? listId : undefined}
        aria-autocomplete="list"
        aria-activedescendant={
          activeHighlight >= 0 ? `${listId}-option-${activeHighlight}` : undefined
        }
        onChange={e => {
          onChange(e.target.value)
          setOpen(true)
          setHighlight(-1)
        }}
        onFocus={() => {
          clearBlurTimer()
          if (value.trim().length >= 3) setOpen(true)
        }}
        onBlur={scheduleClose}
        onKeyDown={e => {
          if (e.key === 'Escape') {
            setOpen(false)
            setHighlight(-1)
            return
          }
          if (!showList && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
            if (value.trim().length >= 3) setOpen(true)
            return
          }
          if (!showList || !hasSuggestions) return

          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setHighlight(prev => (prev + 1) % suggestions.length)
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setHighlight(prev => (prev <= 0 ? suggestions.length - 1 : prev - 1))
          } else if (e.key === 'Enter' && activeHighlight >= 0) {
            e.preventDefault()
            selectSuggestion(suggestions[activeHighlight])
          }
        }}
      />

      {showList ? (
        <ul
          id={listId}
          role="listbox"
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            margin: '4px 0 0',
            padding: 0,
            listStyle: 'none',
            background: 'var(--app-bg)',
            border: '1px solid var(--app-border)',
            borderRadius: 6,
            boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
            maxHeight: 220,
            overflowY: 'auto',
            zIndex: 20,
          }}
        >
          {loading ? (
            <li
              style={{
                padding: '8px 10px',
                fontSize: 13,
                color: 'var(--app-text-muted)',
              }}
            >
              Searching…
            </li>
          ) : null}

          {!loading && hasSuggestions
            ? suggestions.map((s, i) => (
                <li
                  key={s.id}
                  id={`${listId}-option-${i}`}
                  role="option"
                  aria-selected={activeHighlight === i}
                  onMouseDown={e => e.preventDefault()}
                  onClick={() => selectSuggestion(s)}
                  onMouseEnter={() => setHighlight(i)}
                  style={{
                    padding: '8px 10px',
                    fontSize: 13,
                    cursor: 'pointer',
                    background:
                      activeHighlight === i ? 'var(--app-surface)' : 'transparent',
                    color: 'var(--app-text)',
                  }}
                >
                  {s.label}
                </li>
              ))
            : null}

          {!loading && status === 'done' && !hasSuggestions ? (
            <li
              style={{
                padding: '8px 10px',
                fontSize: 13,
                color: 'var(--app-text-muted)',
              }}
            >
              No matches — keep typing or enter manually
            </li>
          ) : null}

          {!loading && status === 'error' ? (
            <li
              style={{
                padding: '8px 10px',
                fontSize: 13,
                color: 'var(--app-text-muted)',
              }}
            >
              {error ?? 'Address search unavailable — enter manually'}
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  )
}
