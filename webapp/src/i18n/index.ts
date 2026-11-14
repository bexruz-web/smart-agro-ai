/**
 * Tiny i18n: one dictionary per language (en is the base), a module-level current language
 * and a t() helper. React components read it through useI18n() so the whole UI re-renders
 * immediately when the language changes. Non-React code (API client errors) calls t() directly.
 *
 * English is the primary language: the base dictionary and the final fallback.
 * Current language = farmer.language (auth / PATCH /me), else the Telegram user's
 * language_code (if it is en / uz / ru), else English.
 */
import { useSyncExternalStore } from 'react'
import { en, type Dictionary, type MessageKey } from './en'
import { ru } from './ru'
import { uz } from './uz'

export type Lang = 'en' | 'uz' | 'ru'
export type { MessageKey }

/** Order of the language switch: ENG · UZB · RUS. */
export const LANGS: Lang[] = ['en', 'uz', 'ru']
export const DEFAULT_LANG: Lang = 'en'
export const DICTIONARIES: Record<Lang, Dictionary> = { en, uz, ru }
/** Labels for the language switch (the same in every language). */
export const LANG_LABEL: Record<Lang, string> = { en: 'ENG', uz: 'UZB', ru: 'RUS' }

export type Params = Record<string, string | number>

/** Normalises any language code ("ru-RU", "EN", "uz-Latn") to a supported Lang, or null. */
export function toLang(code: string | null | undefined): Lang | null {
  if (!code) return null
  const base = code.toLowerCase().split(/[-_]/)[0]
  return (LANGS as string[]).includes(base) ? (base as Lang) : null
}

let current: Lang = DEFAULT_LANG
const listeners = new Set<() => void>()

export function getLang(): Lang {
  return current
}

export function setLang(lang: Lang): void {
  if (lang === current) return
  current = lang
  if (typeof document !== 'undefined') document.documentElement.lang = lang
  listeners.forEach((l) => l())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Replaces {name} placeholders. Unknown placeholders are left as they are. */
export function interpolate(template: string, params?: Params): string {
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m))
}

/** Picks the plural form index for n: ru one|few|many, en one|other, uz has a single form. */
export function pluralIndex(lang: Lang, n: number): number {
  const abs = Math.abs(Math.trunc(n))
  if (lang === 'ru') {
    const m10 = abs % 10
    const m100 = abs % 100
    if (m10 === 1 && m100 !== 11) return 0
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return 1
    return 2
  }
  if (lang === 'en') return abs === 1 ? 0 : 1
  return 0
}

/** Word form for a count from a "one|few|many" entry. */
export function plural(key: MessageKey, n: number, lang: Lang = current): string {
  const forms = DICTIONARIES[lang][key].split('|')
  return forms[Math.min(pluralIndex(lang, n), forms.length - 1)]
}

export function translate(lang: Lang, key: MessageKey, params?: Params): string {
  const s = DICTIONARIES[lang][key] || en[key] || key
  return interpolate(s, params)
}

/** Translates with the current language. */
export function t(key: MessageKey, params?: Params): string {
  return translate(current, key, params)
}

export type TFunction = (key: MessageKey, params?: Params) => string

/** Subscribes the component to language changes. */
export function useI18n(): { lang: Lang; t: TFunction } {
  const lang = useSyncExternalStore(subscribe, getLang, getLang)
  return { lang, t: (key, params) => translate(lang, key, params) }
}
