/**
 * Time formatting. The API sends UTC ISO-8601; the UI always shows Asia/Tashkent (NFR-4).
 * Formatting is done manually (Intl only for the time-zone conversion) so output does
 * not depend on whether the runtime ships Uzbek locale data.
 */

export const TZ = 'Asia/Tashkent'

const MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentyabr', 'oktyabr', 'noyabr', 'dekabr']
// Index = JS getUTCDay() (0 = Sunday).
const WEEKDAYS = ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba']
const WEEKDAYS_SHORT = ['Ya', 'Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh']

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

/** Parses a calendar date "YYYY-MM-DD" (no time zone involved). */
export function parseDateOnly(s: string | null | undefined): { year: number; month: number; day: number; weekday: number } | null {
  if (!s) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s)
  if (!m) return null
  const year = Number(m[1])
  const month = Number(m[2])
  const day = Number(m[3])
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay()
  return { year, month, day, weekday }
}

/** "15-noyabr" or "15-noyabr, 2026" for calendar dates. */
export function formatDateOnly(s: string | null | undefined, withYear = false): string {
  const d = parseDateOnly(s)
  if (!d) return '—'
  return `${d.day}-${MONTHS[d.month - 1]}${withYear ? `, ${d.year}` : ''}`
}

export function weekdayShort(s: string): string {
  const d = parseDateOnly(s)
  return d ? WEEKDAYS_SHORT[d.weekday] : ''
}

export function weekdayLong(s: string): string {
  const d = parseDateOnly(s)
  return d ? WEEKDAYS[d.weekday] : ''
}

/** Whole days between two calendar dates (b − a). */
export function daysBetween(a: string, b: string): number | null {
  const x = parseDateOnly(a)
  const y = parseDateOnly(b)
  if (!x || !y) return null
  return Math.round((Date.UTC(y.year, y.month - 1, y.day) - Date.UTC(x.year, x.month - 1, x.day)) / 86400000)
}

/** Relative time in Uzbek: "hozirgina", "5 daqiqa oldin", "3 soat oldin", "2 kun oldin", "2 soatdan keyin". */
export function formatRelative(v: string | Date | null | undefined, now: Date = new Date()): string {
  if (!v) return '—'
  const d = toDate(v)
  if (!d) return '—'
  const diffSec = Math.round((now.getTime() - d.getTime()) / 1000)
  const future = diffSec < 0
  const s = Math.abs(diffSec)
  if (s < 60) return future ? 'bir necha soniyada' : 'hozirgina'
  let text: string
  if (s < 3600) text = `${Math.floor(s / 60)} daqiqa`
  else if (s < 86400) text = `${Math.floor(s / 3600)} soat`
  else if (s < 86400 * 30) text = `${Math.floor(s / 86400)} kun`
  else if (s < 86400 * 365) text = `${Math.floor(s / (86400 * 30))} oy`
  else text = `${Math.floor(s / (86400 * 365))} yil`
  return future ? `${text}dan keyin` : `${text} oldin`
}

/** True for a bare calendar date "YYYY-MM-DD" (e.g. daily NASA POWER values). */
export function isDateOnly(v: string | null | undefined): boolean {
  return !!v && /^\d{4}-\d{2}-\d{2}$/.test(v)
}

/** Relative days for a calendar date vs today in Tashkent: "bugun", "kecha", "3 kun oldin". */
export function formatRelativeDate(s: string, now: Date = new Date()): string {
  const diff = daysBetween(s, todayTashkent(now))
  if (diff === null) return '—'
  if (diff === 0) return 'bugun'
  if (diff === 1) return 'kecha'
  if (diff > 1) return `${diff} kun oldin`
  if (diff === -1) return 'ertaga'
  return `${-diff} kundan keyin`
}

/**
 * "3 soat oldin · 14.11.2026 14:00" — relative plus absolute Tashkent time.
 * Calendar dates (daily values) are shown without a clock time: "3 kun oldin · 11-noyabr, 2026 (kunlik)".
 */
export function formatObserved(v: string | null | undefined, now: Date = new Date()): string {
  if (!v) return "vaqt noma'lum"
  if (isDateOnly(v)) return `${formatRelativeDate(v, now)} · ${formatDateOnly(v, true)} (kunlik)`
  return `${formatRelative(v, now)} · ${formatDateTime(v)}`
}

/** Instant → "14.11.2026 14:00"; calendar date → "11-noyabr, 2026". */
export function formatWhen(v: string | null | undefined): string {
  if (!v) return '—'
  return isDateOnly(v) ? formatDateOnly(v, true) : formatDateTime(v)
}

/** ISO instant N days before `now` (for timeseries ranges). */
export function isoDaysAgo(days: number, now: Date = new Date()): string {
  return new Date(now.getTime() - days * 86400000).toISOString()
}
