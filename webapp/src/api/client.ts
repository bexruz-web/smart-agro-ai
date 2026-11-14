/**
 * Minimal fetch-based API client.
 * - Bearer token kept in memory and mirrored to sessionStorage (guarded: storage may throw).
 * - On 401 it calls the registered re-authenticator once and retries the request.
 * - Errors are normalised to ApiError with a human-readable Uzbek message.
 */
import { config } from '../config'

const TOKEN_KEY = 'sa_token'

let token: string | null = readStoredToken()
let reauthenticate: (() => Promise<string | null>) | null = null
let reauthInFlight: Promise<string | null> | null = null

function readStoredToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function getToken(): string | null {
  return token
}

export function setToken(t: string | null): void {
  token = t
  try {
    if (t) sessionStorage.setItem(TOKEN_KEY, t)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* private mode / blocked storage: memory only */
  }
}

/** Registers the function used to obtain a fresh token after a 401. */
export function setReauthenticator(fn: (() => Promise<string | null>) | null): void {
  reauthenticate = fn
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

/** Converts FastAPI error bodies ({"detail": str} or 422 list) into a readable message. */
export function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => {
        const item = d as { msg?: string; loc?: unknown[] }
        const loc = Array.isArray(item.loc) ? item.loc.filter((x) => x !== 'body').join('.') : ''
        return item.msg ? (loc ? `${loc}: ${item.msg}` : item.msg) : null
      })
      .filter(Boolean)
    if (msgs.length) return msgs.join('; ')
  }
  if (status === 0) return "Server bilan aloqa yo'q. Internetni tekshiring"
  if (status === 401) return 'Avtorizatsiya talab qilinadi'
  if (status === 403) return "Ruxsat yo'q"
  if (status === 404) return 'Topilmadi'
  if (status === 429) return "Juda ko'p so'rov. Birozdan so'ng qayta urinib ko'ring"
  if (status >= 500) return "Serverda xatolik. Keyinroq qayta urinib ko'ring"
  return `Xatolik (${status})`
}

export interface RawResponse<T> {
  status: number
  data: T
}

type Query = Record<string, string | number | boolean | null | undefined>

function buildUrl(path: string, query?: Query): string {
  let url = config.apiBase + path
  if (query) {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null) params.set(k, String(v))
    const qs = params.toString()
    if (qs) url += (url.includes('?') ? '&' : '?') + qs
  }
  return url
}

async function doFetch(method: string, url: string, body: unknown, auth: boolean): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && token) headers.Authorization = `Bearer ${token}`
  try {
    return await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined })
  } catch (e) {
    throw new ApiError(0, errorMessage(0, null), e)
  }
}

async function parseBody(res: Response): Promise<unknown> {
  if (res.status === 204) return null
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

async function refreshToken(): Promise<string | null> {
  if (!reauthenticate) return null
  // Concurrent 401s share one re-auth round trip.
  if (!reauthInFlight) {
    reauthInFlight = reauthenticate().finally(() => {
      reauthInFlight = null
    })
  }
  return reauthInFlight
}

/** Low-level request returning status + parsed body (needed for 202 handling). */
export async function requestRaw<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Query; auth?: boolean } = {},
): Promise<RawResponse<T>> {
  const auth = options.auth !== false
  const url = buildUrl(path, options.query)
  let res = await doFetch(method, url, options.body, auth)
  if (res.status === 401 && auth) {
    const fresh = await refreshToken().catch(() => null)
    if (fresh) res = await doFetch(method, url, options.body, auth)
  }
  const data = await parseBody(res)
  if (!res.ok) throw new ApiError(res.status, errorMessage(res.status, data), data)
  return { status: res.status, data: data as T }
}

export async function api<T>(method: string, path: string, options: { body?: unknown; query?: Query; auth?: boolean } = {}): Promise<T> {
  return (await requestRaw<T>(method, path, options)).data
}
