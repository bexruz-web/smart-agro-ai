import { lazy, Suspense } from 'react'
import { HashRouter, NavLink, Route, Routes, useLocation } from 'react-router'
import { AuthProvider, type LoginScreenProps } from './auth'
import { config } from './config'
import { isInTelegram } from './telegram'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { DevicesPage } from './pages/DevicesPage'
import { EventsPage } from './pages/EventsPage'
import { FarmLocationPage } from './pages/FarmLocationPage'
import { FieldEditorPage } from './pages/FieldEditorPage'
import { FieldsPage } from './pages/FieldsPage'
import { RotationPage } from './pages/RotationPage'
import { SeasonsPage } from './pages/SeasonsPage'
import { SettingsPage } from './pages/SettingsPage'
import { IconChat, IconLeaf, IconSensor, IconSettings } from './components/icons'
import { Empty, Loading, Page } from './components/ui'

// Chart pages pull in recharts — load them on demand to keep the first paint small.
const HistoryPage = lazy(() => import('./pages/HistoryPage').then((m) => ({ default: m.HistoryPage })))
const ClimatePage = lazy(() => import('./pages/ClimatePage').then((m) => ({ default: m.ClimatePage })))

function LoginScreen({ error, busy, onDemo, onRetryTelegram }: LoginScreenProps) {
  const inTelegram = isInTelegram()
  return (
    <div className="login">
      <div className="login__logo">🌱</div>
      <h1 className="login__title">Smart Agro AI</h1>
      <p className="login__text">NASA ma'lumotlari, dala sensorlari va AI asosida dalangiz uchun aqlli tavsiyalar.</p>
      {error && <div className="state state--error">⚠️ {error}</div>}
      {inTelegram ? (
        <button type="button" className="btn btn--primary btn--block" disabled={busy} onClick={onRetryTelegram}>
          {busy ? 'Kirilmoqda…' : 'Qayta urinish'}
        </button>
      ) : config.allowDemo ? (
        <>
          <button type="button" className="btn btn--primary btn--block" disabled={busy} onClick={onDemo}>
            {busy ? 'Kirilmoqda…' : 'Demo rejimida kirish'}
          </button>
          <p className="login__hint">To'liq ishlash uchun ilovani Telegram bot orqali oching.</p>
        </>
      ) : (
        <p className="login__hint">Ilovani Telegram bot orqali oching.</p>
      )}
    </div>
  )
}

const NAV = [
  { to: '/', label: 'Dalalar', Icon: IconLeaf, end: true },
  { to: '/chat', label: 'AI agronom', Icon: IconChat, end: false },
  { to: '/devices', label: 'Qurilmalar', Icon: IconSensor, end: false },
  { to: '/settings', label: 'Sozlamalar', Icon: IconSettings, end: false },
]

function BottomNav() {
  return (
    <nav className="bottom-nav" aria-label="Asosiy menyu">
      {NAV.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `bottom-nav__item ${isActive ? 'is-active' : ''}`}>
          <span className="bottom-nav__icon">
            <n.Icon size={22} />
          </span>
          <span className="bottom-nav__label">{n.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}

/** Full-screen map screens hide the bottom navigation (and use MainButton for saving). */
function Shell() {
  const { pathname } = useLocation()
  const fullScreen = /^\/fields\/(new|\d+\/edit)$/.test(pathname) || pathname === '/location'
  return (
    <div className={`app ${fullScreen ? 'app--fullscreen' : 'app--with-nav'}`}>
      <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<FieldsPage />} />
        <Route path="/location" element={<FarmLocationPage />} />
        <Route path="/fields/new" element={<FieldEditorPage />} />
        <Route path="/fields/:id" element={<DashboardPage />} />
        <Route path="/fields/:id/edit" element={<FieldEditorPage />} />
        <Route path="/fields/:id/history" element={<HistoryPage />} />
        <Route path="/fields/:id/climate" element={<ClimatePage />} />
        <Route path="/fields/:id/rotation" element={<RotationPage />} />
        <Route path="/fields/:id/seasons" element={<SeasonsPage />} />
        <Route path="/fields/:id/events" element={<EventsPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route
          path="*"
          element={
            <Page title="Sahifa topilmadi" back="/">
              <Empty>Bunday sahifa yo'q.</Empty>
            </Page>
          }
        />
      </Routes>
      </Suspense>
      {!fullScreen && <BottomNav />}
    </div>
  )
}

export default function App() {
  return (
    <HashRouter>
      <AuthProvider loginScreen={(p) => <LoginScreen {...p} />}>
        <Shell />
      </AuthProvider>
    </HashRouter>
  )
}
