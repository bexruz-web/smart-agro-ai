/**
 * Thin typed wrapper around window.Telegram.WebApp.
 *
 * Every function is safe to call in a plain browser (no Telegram): it either
 * no-ops or returns a sensible fallback, so business code never has to check
 * `window.Telegram` itself.
 */

import { config } from './config'

type Callback = () => void

interface TgBottomButton {
  text: string
  isVisible: boolean
  isActive: boolean
  setText(text: string): TgBottomButton
  show(): TgBottomButton
  hide(): TgBottomButton
  enable(): TgBottomButton
  disable(): TgBottomButton
  showProgress(leaveActive?: boolean): TgBottomButton
  hideProgress(): TgBottomButton
  onClick(cb: Callback): TgBottomButton
  offClick(cb: Callback): TgBottomButton
}

interface TgBackButton {
  isVisible: boolean
  show(): TgBackButton
  hide(): TgBackButton
  onClick(cb: Callback): TgBackButton
  offClick(cb: Callback): TgBackButton
}

export interface TgLocationData {
  latitude: number
  longitude: number
  altitude: number | null
  course: number | null
  speed: number | null
  horizontal_accuracy: number | null
  vertical_accuracy: number | null
  course_accuracy: number | null
  speed_accuracy: number | null
}

interface TgLocationManager {
  isInited: boolean
  isLocationAvailable: boolean
  isAccessRequested: boolean
  isAccessGranted: boolean
  init(cb?: Callback): TgLocationManager
  getLocation(cb: (data: TgLocationData | null) => void): TgLocationManager
  openSettings(): TgLocationManager
}

interface TgWebApp {
  initData: string
  version: string
  platform: string
  colorScheme: 'light' | 'dark'
  themeParams: Record<string, string | undefined>
  isExpanded: boolean
  ready(): void
  expand(): void
  close(): void
  isVersionAtLeast(version: string): boolean
  disableVerticalSwipes?: () => void
  enableVerticalSwipes?: () => void
  setHeaderColor?: (color: string) => void
  setBackgroundColor?: (color: string) => void
  setBottomBarColor?: (color: string) => void
  onEvent(event: string, cb: Callback): void
  offEvent(event: string, cb: Callback): void
  showAlert?: (message: string, cb?: Callback) => void
  openLink?: (url: string, options?: { try_instant_view?: boolean }) => void
  showConfirm?: (message: string, cb?: (ok: boolean) => void) => void
  MainButton: TgBottomButton
  BackButton: TgBackButton
  LocationManager?: TgLocationManager
  HapticFeedback?: {
    impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
    notificationOccurred(type: 'error' | 'success' | 'warning'): void
  }
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TgWebApp }
  }
}

function webApp(): TgWebApp | undefined {
  return typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined
}

function atLeast(version: string): boolean {
  const wa = webApp()
  try {
    return !!wa && typeof wa.isVersionAtLeast === 'function' && wa.isVersionAtLeast(version)
  } catch {
    return false
  }
}

/** Signed init data (empty string in a plain browser). */
export function getInitData(): string {
  return webApp()?.initData ?? ''
}

/** True only when actually running inside a Telegram client (initData present). */
export function isInTelegram(): boolean {
  return getInitData().length > 0
}

/** Current color scheme: Telegram's, else the OS preference. */
export function getColorScheme(): 'light' | 'dark' {
  const wa = webApp()
  if (isInTelegram() && wa?.colorScheme) return wa.colorScheme
  if (typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark'
  return 'light'
}

/** Theme actually applied: the brand light palette unless VITE_THEME_MODE=auto (then follow Telegram/OS). */
export function getAppliedTheme(): 'light' | 'dark' {
  return config.themeMode === 'auto' ? getColorScheme() : 'light'
}

function readHex(name: string): string | null {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return /^#[0-9a-fA-F]{6}$/.test(v) ? v : null
}

function applyTheme(): void {
  const root = document.documentElement
  root.dataset.theme = getAppliedTheme()
  root.dataset.telegram = isInTelegram() ? 'true' : 'false'
  const wa = webApp()
  if (!isInTelegram() || !wa) return
  // Paint Telegram's header / background / bottom bar with our brand colours.
  const bg = readHex('--color-bg')
  const bar = readHex('--color-card')
  try {
    if (bg && atLeast('6.9')) wa.setHeaderColor?.(bg)
    else if (atLeast('6.1')) wa.setHeaderColor?.(getAppliedTheme() === 'light' ? 'bg_color' : 'secondary_bg_color')
    if (bg && atLeast('6.1')) wa.setBackgroundColor?.(bg)
    if (bar && atLeast('7.10')) wa.setBottomBarColor?.(bar)
  } catch {
    /* older clients */
  }
}

/** Call once on startup: ready(), expand(), disable swipe-to-close, apply theme. */
export function initTelegram(): void {
  const wa = webApp()
  applyTheme()
  // Follow OS theme changes in a plain browser.
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', applyTheme)
  if (!wa || !isInTelegram()) return
  try {
    wa.ready()
    wa.expand()
    // Bot API 7.7+: prevents the Mini App from closing while the user drags on the map (TG-7).
    if (atLeast('7.7') && typeof wa.disableVerticalSwipes === 'function') wa.disableVerticalSwipes()
    wa.onEvent('themeChanged', applyTheme)
  } catch (e) {
    console.warn('Telegram init failed', e)
  }
}

// ---------------------------------------------------------------- MainButton

/** Shows Telegram MainButton. Returns false in a plain browser (caller renders its own button). */
export function showMainButton(text: string, onClick: Callback, opts: { enabled: boolean; progress?: boolean }): boolean {
  const wa = webApp()
  if (!wa || !isInTelegram() || !wa.MainButton) return false
  const mb = wa.MainButton
  mb.setText(text)
  if (opts.enabled) mb.enable()
  else mb.disable()
  if (opts.progress) mb.showProgress(false)
  else mb.hideProgress()
  mb.onClick(onClick)
  mb.show()
  return true
}

/** Updates text/state of an already shown MainButton. */
export function updateMainButton(text: string, opts: { enabled: boolean; progress?: boolean }): void {
  const wa = webApp()
  if (!wa || !isInTelegram() || !wa.MainButton) return
  const mb = wa.MainButton
  mb.setText(text)
  if (opts.enabled) mb.enable()
  else mb.disable()
  if (opts.progress) mb.showProgress(false)
  else mb.hideProgress()
}

export function hideMainButton(onClick?: Callback): void {
  const wa = webApp()
  if (!wa || !isInTelegram() || !wa.MainButton) return
  if (onClick) wa.MainButton.offClick(onClick)
  wa.MainButton.hideProgress()
  wa.MainButton.hide()
}

// ---------------------------------------------------------------- BackButton

/** Shows Telegram BackButton. Returns false when not available (caller renders on-page back). */
export function showBackButton(onClick: Callback): boolean {
  const wa = webApp()
  if (!wa || !isInTelegram() || !wa.BackButton || !atLeast('6.1')) return false
  wa.BackButton.onClick(onClick)
  wa.BackButton.show()
  return true
}

export function hideBackButton(onClick?: Callback): void {
  const wa = webApp()
  if (!wa || !isInTelegram() || !wa.BackButton || !atLeast('6.1')) return
  if (onClick) wa.BackButton.offClick(onClick)
  wa.BackButton.hide()
}

export function hasNativeBackButton(): boolean {
  const wa = webApp()
  return !!wa && isInTelegram() && !!wa.BackButton && atLeast('6.1')
}

// ---------------------------------------------------------------- Links

/** Opens an external link: Telegram's in-app browser when available, else a new tab. */
export function openExternalLink(url: string): void {
  const wa = webApp()
  if (wa && isInTelegram() && typeof wa.openLink === 'function') {
    wa.openLink(url)
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

// ---------------------------------------------------------------- Dialogs / haptics

export function confirmDialog(message: string): Promise<boolean> {
  const wa = webApp()
  if (wa && isInTelegram() && wa.showConfirm && atLeast('6.2')) {
    return new Promise((resolve) => wa.showConfirm!(message, (ok) => resolve(!!ok)))
  }
  return Promise.resolve(window.confirm(message))
}

export function haptic(type: 'success' | 'error' | 'warning'): void {
  try {
    if (atLeast('6.1')) webApp()?.HapticFeedback?.notificationOccurred(type)
  } catch {
    /* ignore */
  }
}

// ---------------------------------------------------------------- Location

export interface GeoFix {
  lat: number
  lon: number
  /** Horizontal accuracy in meters, if known. */
  accuracy: number | null
  source: 'telegram' | 'browser'
}

export class LocationError extends Error {
  readonly code: 'denied' | 'unavailable' | 'timeout'
  constructor(code: 'denied' | 'unavailable' | 'timeout', message: string) {
    super(message)
    this.code = code
  }
}

function telegramLocation(): Promise<GeoFix | null> {
  const wa = webApp()
  const lm = wa?.LocationManager
  // LocationManager exists since Bot API 8.0.
  if (!wa || !isInTelegram() || !lm || !atLeast('8.0')) return Promise.resolve(null)
  return new Promise((resolve) => {
    const request = () => {
      if (!lm.isLocationAvailable) return resolve(null)
      lm.getLocation((data) => {
        if (!data) return resolve(null) // denied or failed → let the browser API try
        resolve({ lat: data.latitude, lon: data.longitude, accuracy: data.horizontal_accuracy ?? null, source: 'telegram' })
      })
    }
    try {
      if (lm.isInited) request()
      else lm.init(request)
    } catch {
      resolve(null)
    }
  })
}

function browserLocation(): Promise<GeoFix> {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      reject(new LocationError('unavailable', "Qurilmada GPS/joylashuv xizmati mavjud emas"))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy ?? null, source: 'browser' }),
      (err) => {
        if (err.code === err.PERMISSION_DENIED)
          reject(new LocationError('denied', "Joylashuvga ruxsat berilmadi. Sozlamalardan ruxsat bering yoki xaritada tanlang"))
        else if (err.code === err.TIMEOUT) reject(new LocationError('timeout', "Joylashuvni aniqlash vaqti tugadi, qayta urinib ko'ring"))
        else reject(new LocationError('unavailable', "Joylashuvni aniqlab bo'lmadi"))
      },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
    )
  })
}

/**
 * Current GPS position (TG-3 order): Telegram LocationManager (Bot API 8.0+)
 * → browser navigator.geolocation. Manual map pick is the caller's fallback.
 */
export async function getCurrentLocation(): Promise<GeoFix> {
  const tg = await telegramLocation()
  if (tg) return tg
  return browserLocation()
}
