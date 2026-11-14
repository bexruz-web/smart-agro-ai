/**
 * Authentication (UI language follows farmer.language as soon as the farmer is known):
 *  - inside Telegram (initData present) → POST /auth/telegram (server verifies the signature);
 *  - plain browser → "Demo rejimida kirish" button → POST /auth/demo (if VITE_ALLOW_DEMO !== "false").
 * On a 401 the API client re-authenticates once with the same method.
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { ApiError, getToken, setReauthenticator, setToken } from './api/client'
import { authDemo, authTelegram, getMe } from './api/endpoints'
import type { AuthResponse, Farmer } from './api/types'
import { config } from './config'
import { setLang, t, toLang } from './i18n'
import { getInitData, isInTelegram } from './telegram'

type Status = 'loading' | 'need-login' | 'ready'
type Mode = 'telegram' | 'demo'

interface AuthContextValue {
  farmer: Farmer
  mode: Mode
  setFarmer: (f: Farmer) => void
  refreshFarmer: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

const MODE_KEY = 'sa_mode'

function storeMode(mode: Mode | null) {
  try {
    if (mode) sessionStorage.setItem(MODE_KEY, mode)
    else sessionStorage.removeItem(MODE_KEY)
  } catch {
    /* ignore */
  }
}

function readMode(): Mode | null {
  try {
    const m = sessionStorage.getItem(MODE_KEY)
    return m === 'demo' || m === 'telegram' ? m : null
  } catch {
    return null
  }
}

async function loginWith(mode: Mode): Promise<AuthResponse> {
  const res = mode === 'telegram' ? await authTelegram(getInitData()) : await authDemo()
  setToken(res.access_token)
  storeMode(mode)
  setReauthenticator(async () => {
    try {
      const r = mode === 'telegram' ? await authTelegram(getInitData()) : await authDemo()
      setToken(r.access_token)
      return r.access_token
    } catch {
      setToken(null)
      return null
    }
  })
  return res
}

/** Switches the UI to the farmer's saved language (if the server sent a supported one). */
function applyLanguage(f: Farmer) {
  const lang = toLang(f.language)
  if (lang) setLang(lang)
}

export function AuthProvider({ children, loginScreen }: { children: ReactNode; loginScreen: (p: LoginScreenProps) => ReactNode }) {
  const [status, setStatus] = useState<Status>('loading')
  const [farmer, setFarmerState] = useState<Farmer | null>(null)
  const setFarmer = useCallback((f: Farmer) => {
    applyLanguage(f)
    setFarmerState(f)
  }, [])
  const [mode, setMode] = useState<Mode>(isInTelegram() ? 'telegram' : 'demo')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const login = useCallback(async (m: Mode) => {
    setBusy(true)
    setError(null)
    try {
      const res = await loginWith(m)
      setMode(m)
      setFarmer(res.farmer)
      setStatus('ready')
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : t('login.error')
      setError(m === 'demo' && e instanceof ApiError && (e.status === 403 || e.status === 404) ? t('login.demoDisabled') : msg)
      setStatus('need-login')
    } finally {
      setBusy(false)
    }
  }, [setFarmer])

  useEffect(() => {
    let alive = true
    ;(async () => {
      if (isInTelegram()) {
        await login('telegram')
        return
      }
      // Plain browser: reuse a demo session from this tab if it is still valid.
      if (getToken() && readMode() === 'demo' && config.allowDemo) {
        setReauthenticator(async () => {
          try {
            const r = await authDemo()
            setToken(r.access_token)
            return r.access_token
          } catch {
            return null
          }
        })
        try {
          const me = await getMe()
          if (!alive) return
          setMode('demo')
          setFarmer(me)
          setStatus('ready')
          return
        } catch {
          setToken(null)
          storeMode(null)
        }
      }
      if (alive) setStatus('need-login')
    })()
    return () => {
      alive = false
    }
  }, [login, setFarmer])

  const refreshFarmer = useCallback(async () => {
    setFarmer(await getMe())
  }, [setFarmer])

  if (status === 'loading') {
    return (
      <div className="splash">
        <div className="splash__logo">🌱</div>
        <div className="splash__title">{t('app.name')}</div>
        <div className="spinner" aria-label={t('common.loading')} />
      </div>
    )
  }

  if (status === 'need-login' || !farmer) {
    return <>{loginScreen({ error, busy, onDemo: () => login('demo'), onRetryTelegram: () => login('telegram') })}</>
  }

  return <AuthContext.Provider value={{ farmer, mode, setFarmer, refreshFarmer }}>{children}</AuthContext.Provider>
}

export interface LoginScreenProps {
  error: string | null
  busy: boolean
  onDemo: () => void
  onRetryTelegram: () => void
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
