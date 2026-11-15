/**
 * Time formatting. The API sends UTC ISO-8601; the UI always shows Asia/Tashkent.
 * Formatting is done manually (Intl only for the time-zone conversion) so output does
 * not depend on the runtime's locale data.
 */
import { getLang, plural, translate, type Lang, type MessageKey } from '../i18n'

export const TZ = 'Asia/Tashkent'

const partsFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

interface Parts {
  year: number
  month: number
  day: number
  hour: number
  minute: number
}

function toDate(v: string | Date): Date | null {
  const d = v instanceof Date ? v : new Date(v)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Wall-clock parts of an instant in Asia/Tashkent. */
export function tashkentParts(v: string | Date): Parts | null {
  const d = toDate(v)
  if (!d) return null
  const out: Record<string, number> = {}
  for (const p of partsFormatter.formatToParts(d)) {
    if (p.type !== 'literal') out[p.type] = Number(p.value)
  }
  return { year: out.year, month: out.month, day: out.day, hour: out.hour % 24, minute: out.minute }
}

const pad = (n: number) => String(n).padStart(2, '0')

/** "14.11.2026 14:00" in Tashkent time. */
export function formatDateTime(v: string | Date | null | undefined): string {
  if (!v) return '—'
  const p = tashkentParts(v)
  if (!p) return '—'
  return `${pad(p.day)}.${pad(p.month)}.${p.year} ${pad(p.hour)}:${pad(p.minute)}`
}

/** "14:00" in Tashkent time. */
export function formatTime(v: string | Date | null | undefined): string {
  if (!v) return '—'
  const p = tashkentParts(v)
  return p ? `${pad(p.hour)}:${pad(p.minute)}` : '—'
}

/** Today's calendar date in Tashkent as "YYYY-MM-DD" (for date inputs). */
export function todayTashkent(now: Date = new Date()): string {
  const p = tashkentParts(now)!
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`
}

/** True for a calendar date "YYYY-MM-DD" that exists. */
export function isValidDateOnly(s: string | null | undefined): boolean {
  const m = s ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(s) : null
  if (!m) return false
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const dt = new Date(Date.UTC(y, mo - 1, d))
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d
}

/**
 * A calendar date "YYYY-MM-DD" as a short label in the UI language: "Today" / "Tomorrow"
 * (Tashkent calendar), otherwise weekday + day.month: "Wed 18.11" · "Chor 18.11" · "Ср 18.11".
 */
export function formatDay(date: string | null | undefined, lang: Lang = getLang(), now: Date = new Date()): string {
  if (!date || !isValidDateOnly(date)) return '—'
  const [y, m, d] = date.split('-').map(Number)
  const day = new Date(Date.UTC(y, m - 1, d))
  const today = todayTashkent(now)
  if (date === today) return translate(lang, 'time.today')
  const [ty, tm, td] = today.split('-').map(Number)
  if (day.getTime() - Date.UTC(ty, tm - 1, td) === 86400000) return translate(lang, 'time.tomorrow')
  const weekday = translate(lang, 'time.weekdays').split('|')[day.getUTCDay()] ?? ''
  return `${weekday} ${pad(d)}.${pad(m)}`.trim()
}

/** Minutes elapsed since an instant (negative for the future); null for invalid input. */
export function minutesSince(v: string | null | undefined, now: Date = new Date()): number | null {
  if (!v) return null
  const d = toDate(v)
  return d ? (now.getTime() - d.getTime()) / 60000 : null
}

const UNITS: { sec: number; key: MessageKey }[] = [
  { sec: 86400 * 365, key: 'time.year' },
  { sec: 86400 * 30, key: 'time.month' },
  { sec: 86400, key: 'time.day' },
  { sec: 3600, key: 'time.hour' },
  { sec: 60, key: 'time.minute' },
]

/**
 * Relative time in the UI language: "5 daqiqa oldin" / "5 минут назад" / "5 minutes ago",
 * "hozirgina" for < 1 minute.
 */
export function formatRelative(v: string | Date | null | undefined, now: Date = new Date(), lang: Lang = getLang()): string {
  if (!v) return '—'
  const d = toDate(v)
  if (!d) return '—'
  const diffSec = Math.round((now.getTime() - d.getTime()) / 1000)
  const future = diffSec < 0
  const s = Math.abs(diffSec)
  if (s < 60) return translate(lang, future ? 'time.soon' : 'time.justNow')
  const unit = UNITS.find((u) => s >= u.sec)!
  const n = Math.floor(s / unit.sec)
  return translate(lang, future ? 'time.in' : 'time.ago', { n, unit: plural(unit.key, n, lang) })
}
