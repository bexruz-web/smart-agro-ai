/** Typed wrappers for every endpoint in docs/API_CONTRACT.md used by the Mini App. */
import { api, requestRaw } from './client'
import type {
  AuthResponse,
  ChatMessage,
  ChatReply,
  ClimateShift,
  ClimateShiftResult,
  Crop,
  Dashboard,
  Device,
  DeviceCreated,
  Farmer,
  FarmerPatch,
  FeedbackAction,
  Field,
  FieldEvent,
  FieldInput,
  HarvestInput,
  Recommendation,
  RotationPlan,
  Season,
  SoilTexture,
  Timeseries,
} from './types'

// Auth
export const authTelegram = (initData: string) =>
  api<AuthResponse>('POST', '/auth/telegram', { body: { init_data: initData }, auth: false })
export const authDemo = () => api<AuthResponse>('POST', '/auth/demo', { auth: false })

// Profile
export const getMe = () => api<Farmer>('GET', '/me')
export const patchMe = (patch: FarmerPatch) => api<Farmer>('PATCH', '/me', { body: patch })

// Reference data
export const getCrops = () => api<Crop[]>('GET', '/crops')
export const getSoilTextures = () => api<SoilTexture[]>('GET', '/soil-textures')

// Fields
export const getFields = () => api<Field[]>('GET', '/fields')
export const getField = (id: number) => api<Field>('GET', `/fields/${id}`)
export const createField = (input: FieldInput) => api<Field>('POST', '/fields', { body: input })
export const updateField = (id: number, input: Partial<FieldInput>) => api<Field>('PATCH', `/fields/${id}`, { body: input })
export const deleteField = (id: number) => api<null>('DELETE', `/fields/${id}`)

// Dashboard & data
export const getDashboard = (id: number) => api<Dashboard>('GET', `/fields/${id}/dashboard`)
export const getTimeseries = (id: number, metric: string, from: string, to: string) =>
  api<Timeseries>('GET', `/fields/${id}/timeseries`, { query: { metric, from, to } })

/** Climate shift may answer 202 {"status":"pending"} while NASA POWER data is being fetched. */
export async function getClimateShift(id: number): Promise<ClimateShiftResult> {
  const res = await requestRaw<ClimateShift | { status: string }>('GET', `/fields/${id}/climate-shift`)
  if (res.status === 202 || (res.data as { status?: string } | null)?.status === 'pending') return { status: 'pending' }
  return { status: 'ready', data: res.data as ClimateShift }
}

// Recommendations
export const getRecommendations = (id: number, status?: string) =>
  api<Recommendation[]>('GET', `/fields/${id}/recommendations`, { query: { status } })
export const sendFeedback = (recId: number, action: FeedbackAction, comment: string | null = null) =>
  api<{ ok: boolean }>('POST', `/recommendations/${recId}/feedback`, { body: { action, comment } })

// Seasons, events, rotation
export const getSeasons = (id: number) => api<Season[]>('GET', `/fields/${id}/seasons`)
export const startSeason = (id: number, crop: string, plantingDate: string) =>
  api<Season>('POST', `/fields/${id}/seasons`, { body: { crop, planting_date: plantingDate } })
export const recordHarvest = (seasonId: number, input: HarvestInput) =>
  api<Season>('PATCH', `/seasons/${seasonId}/harvest`, { body: input })
export const getEvents = (id: number) => api<FieldEvent[]>('GET', `/fields/${id}/events`)
export const addEvent = (id: number, ev: FieldEvent) => api<FieldEvent>('POST', `/fields/${id}/events`, { body: ev })
export const getRotationPlan = (id: number) => api<RotationPlan>('GET', `/fields/${id}/rotation-plan`)

// Chat
export const sendChat = (message: string, fieldId: number | null) =>
  api<ChatReply>('POST', '/chat', { body: { message, field_id: fieldId } })
export const getChatHistory = () => api<ChatMessage[]>('GET', '/chat/history')

// Devices
export const getDevices = () => api<Device[]>('GET', '/devices')
export const createDevice = (name: string, fieldId: number) =>
  api<DeviceCreated>('POST', '/devices', { body: { name, field_id: fieldId } })
export const deleteDevice = (id: number) => api<null>('DELETE', `/devices/${id}`)

// Demo (DEMO_MODE=true or admin only)
export type DemoScenario = 'drought' | 'heavy_rain' | 'sensor_fault' | 'normal'
export interface DemoScenarioResult {
  scenario: string
  alerts: string[]
  sent?: string[]
  llm_status?: string
}
export const runDemoScenario = (scenario: DemoScenario, fieldId: number) =>
  api<DemoScenarioResult>('POST', `/admin/demo/${scenario}`, { query: { field_id: fieldId } })
