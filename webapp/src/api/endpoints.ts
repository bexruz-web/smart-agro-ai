/** Typed wrappers for the endpoints the Mini App uses (docs/API_CONTRACT_V2.md). */
import type { Lang } from '../i18n'
import { api } from './client'
import type {
  AgronomInfo,
  AuthResponse,
  ChatReply,
  Farmer,
  FarmerPatch,
  Field,
  FieldInput,
  Options,
  RefItem,
} from './types'

// Auth
export const authTelegram = (initData: string) =>
  api<AuthResponse>('POST', '/auth/telegram', { body: { init_data: initData }, auth: false })
export const authDemo = () => api<AuthResponse>('POST', '/auth/demo', { auth: false })

// Profile
export const getMe = () => api<Farmer>('GET', '/me')
export const patchMe = (patch: FarmerPatch) => api<Farmer>('PATCH', '/me', { body: patch })

// Localized reference data — cached per language for the session (failed requests are not cached).
const refCache = new Map<string, Promise<unknown>>()
function cached<T>(key: string, load: () => Promise<T>): Promise<T> {
  let p = refCache.get(key) as Promise<T> | undefined
  if (!p) {
    p = load()
    refCache.set(key, p)
    p.catch(() => refCache.delete(key))
  }
  return p
}
export const getCrops = (lang: Lang) => cached(`crops:${lang}`, () => api<RefItem[]>('GET', '/crops', { query: { lang } }))
export const getSoilTextures = (lang: Lang) =>
  cached(`soil:${lang}`, () => api<RefItem[]>('GET', '/soil-textures', { query: { lang } }))
export const getOptions = (lang: Lang) => cached(`options:${lang}`, () => api<Options>('GET', '/options', { query: { lang } }))

// Fields
export const getFields = () => api<Field[]>('GET', '/fields')
export const getField = (id: number) => api<Field>('GET', `/fields/${id}`)
export const createField = (input: FieldInput) => api<Field>('POST', '/fields', { body: input })
export const updateField = (id: number, input: Partial<FieldInput>) => api<Field>('PATCH', `/fields/${id}`, { body: input })
export const deleteField = (id: number) => api<null>('DELETE', `/fields/${id}`)

// AI Agronom (per field)
export const getAgronom = (id: number, lang: Lang) => api<AgronomInfo>('GET', `/fields/${id}/agronom`, { query: { lang } })
export const sendChat = (message: string, fieldId: number) =>
  api<ChatReply>('POST', '/chat', { body: { message, field_id: fieldId } })
