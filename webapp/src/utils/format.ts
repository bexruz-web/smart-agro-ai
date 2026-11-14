/** Number formatting / parsing that follows the UI language (decimal comma in uz/ru). */
import { getLang, type Lang } from '../i18n'

const SEPARATORS: Record<Lang, { decimal: string; group: string }> = {
  uz: { decimal: ',', group: ' ' },
  ru: { decimal: ',', group: ' ' },
  en: { decimal: '.', group: ',' },
}

/**
 * Number with up to `digits` decimals (trailing zeros dropped); "—" for null/NaN.
 * uz/ru: "76,23" and "5 000"; en: "76.23" and "5,000".
 */
export function fmtNum(v: number | null | undefined, digits = 1, lang: Lang = getLang()): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  // Round half away from zero on the decimal value (2.15 → 2.2, not 2.1 from binary float error).
  const f = 10 ** digits
  const rounded = (Math.sign(v) * Math.round(Number((Math.abs(v) * f).toPrecision(12)))) / f || 0
  const [int, frac] = Math.abs(rounded).toFixed(digits).split('.')
  const sep = SEPARATORS[lang]
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, sep.group)
  const fracTrim = frac ? frac.replace(/0+$/, '') : ''
  return `${rounded < 0 ? '−' : ''}${grouped}${fracTrim ? sep.decimal + fracTrim : ''}`
}

/**
 * Parses a number typed by a farmer. Accepts a decimal comma or dot ("76,23", "76.23")
 * and spaces ("1 250,5"). Returns null for anything that is not a single plain number.
 */
export function parseDecimal(input: string): number | null {
  const s = input.trim().replace(/[\s ]/g, '').replace(',', '.')
  if (!/^[+]?(\d+(\.\d*)?|\.\d+)$/.test(s)) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

/** Number → text for an input field in the UI language ("76,23"). */
export function decimalToInput(v: number | null | undefined, lang: Lang = getLang()): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return ''
  const s = String(Math.round(v * 10000) / 10000)
  return SEPARATORS[lang].decimal === ',' ? s.replace('.', ',') : s
}
