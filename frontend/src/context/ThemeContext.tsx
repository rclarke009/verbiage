import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'

export const THEME_STORAGE_KEY = 'trueai-theme-preference'

interface ThemeCtx {
  preference: ThemePreference
  setPreference: (preference: ThemePreference) => void
}

const Ctx = createContext<ThemeCtx | null>(null)

function readStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  } catch {
    /* ignore */
  }
  return 'system'
}

function applyThemePreference(preference: ThemePreference) {
  document.documentElement.setAttribute('data-theme', preference)
  document.documentElement.style.colorScheme =
    preference === 'system' ? '' : preference
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readStoredPreference)

  useEffect(() => {
    applyThemePreference(preference)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, preference)
    } catch {
      /* ignore */
    }
  }, [preference])

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next)
  }, [])

  const value = useMemo(
    () => ({ preference, setPreference }),
    [preference, setPreference],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useTheme() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
