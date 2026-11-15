import { useEffect } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router'
import { AuthProvider, useAuth, type LoginScreenProps } from './auth'
import { config } from './config'
import { useI18n } from './i18n'
import { isInTelegram } from './telegram'
import { IconMap, IconPlus, IconSettings } from './components/icons'
import { Empty, Page } from './components/ui'
import { AgronomPage } from './pages/AgronomPage'
import { DashboardPage } from './pages/DashboardPage'
import { FieldFormPage } from './pages/FieldFormPage'
import { FieldPage } from './pages/FieldPage'
import { RegionPage } from './pages/RegionPage'
import { SettingsPage } from './pages/SettingsPage'

function LoginScreen({ error, busy, onDemo, onRetryTelegram }: LoginScreenProps) {
  const { t } = useI18n()
  const inTelegram = isInTelegram()
  return (
    <div className="login">
      <div className="login__logo">🌱</div>
      <h1 className="login__title">{t('app.name')}</h1>
      <p className="login__text">{t('login.tagline')}</p>
      {error && <div className="state state--error">⚠️ {error}</div>}
      {inTelegram ? (
        <button type="button" className="btn btn--primary btn--block" disabled={busy} onClick={onRetryTelegram}>
          {busy ? t('login.signingIn') : t('common.retry')}
        </button>
      ) : config.allowDemo ? (
        <>
          <button type="button" className="btn btn--primary btn--block" disabled={busy} onClick={onDemo}>
            {busy ? t('login.signingIn') : t('login.demo')}
          </button>
          <p className="login__hint">{t('login.openInTelegramFull')}</p>
        </>
      ) : (
        <p className="login__hint">{t('login.openInTelegram')}</p>
      )}
    </div>
  )
}

type Tab = 'dashboard' | 'add' | 'settings'

function activeTab(pathname: string): Tab | null {
  if (pathname === '/fields/new') return 'add'
  if (pathname === '/settings') return 'settings'
  if (pathname === '/' || pathname.startsWith('/fields/')) return 'dashboard'
  return null
}

/** Exactly 3 tabs: Dashboard · Qo'shish (+) · Sozlamalar. */
function BottomNav() {
  const { t } = useI18n()
  const { pathname } = useLocation()
  const active = activeTab(pathname)
  return (
    <nav className="bottom-nav" aria-label={t('nav.aria')}>
      <Link to="/" className={`bottom-nav__item ${active === 'dashboard' ? 'is-active' : ''}`} aria-current={active === 'dashboard' ? 'page' : undefined}>
        <span className="bottom-nav__icon">
          <IconMap size={22} />
        </span>
        <span className="bottom-nav__label">{t('nav.dashboard')}</span>
      </Link>
      <Link to="/fields/new" className={`bottom-nav__item bottom-nav__item--add ${active === 'add' ? 'is-active' : ''}`} aria-current={active === 'add' ? 'page' : undefined}>
        <span className="bottom-nav__plus">
          <IconPlus size={24} strokeWidth={2.4} />
        </span>
        <span className="bottom-nav__label">{t('nav.add')}</span>
      </Link>
      <Link to="/settings" className={`bottom-nav__item ${active === 'settings' ? 'is-active' : ''}`} aria-current={active === 'settings' ? 'page' : undefined}>
        <span className="bottom-nav__icon">
          <IconSettings size={22} />
        </span>
        <span className="bottom-nav__label">{t('nav.settings')}</span>
      </Link>
    </nav>
  )
}

function NotFound() {
  const { t } = useI18n()
  return (
    <Page title={t('common.notFound')} back="/">
      <Empty>{t('common.notFoundText')}</Empty>
    </Page>
  )
}

function Shell() {
  const { farmer } = useAuth()
  const { pathname } = useLocation()
  useI18n() // re-render the shell on language change
  // A new screen always starts at the top.
  useEffect(() => window.scrollTo(0, 0), [pathname])

  // First entry: the farmer has not chosen a region yet.
  if (!farmer.farm_location) {
    return (
      <div className="app app--fullscreen">
        <RegionPage />
      </div>
    )
  }

  return (
    <div className="app app--with-nav">
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/fields/new" element={<FieldFormPage />} />
        <Route path="/fields/:id" element={<FieldPage />} />
        <Route path="/fields/:id/edit" element={<FieldFormPage />} />
        <Route path="/fields/:id/agronom" element={<AgronomPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <BottomNav />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider loginScreen={(p) => <LoginScreen {...p} />}>
        <Shell />
      </AuthProvider>
    </BrowserRouter>
  )
}
