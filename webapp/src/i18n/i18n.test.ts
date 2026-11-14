import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { en } from './en'
import { DEFAULT_LANG, DICTIONARIES, LANGS, LANG_LABEL, interpolate, plural, pluralIndex, setLang, t, toLang, translate } from './index'

type Key = keyof typeof en
/** English is the base dictionary. */
const baseKeys = Object.keys(en).sort()
const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()

describe('dictionaries are complete', () => {
  for (const lang of LANGS) {
    it(`${lang}: has exactly the same keys as en (base)`, () => {
      expect(Object.keys(DICTIONARIES[lang]).sort()).toEqual(baseKeys)
    })

    it(`${lang}: every value is a non-empty string`, () => {
      for (const k of baseKeys) {
        const v = DICTIONARIES[lang][k as Key]
        expect(typeof v, k).toBe('string')
        expect(v.trim().length, k).toBeGreaterThan(0)
      }
    })

    it(`${lang}: placeholders match en`, () => {
      for (const k of baseKeys) {
        expect(placeholders(DICTIONARIES[lang][k as Key]), `${lang}:${k}`).toEqual(placeholders(en[k as Key]))
      }
    })
  }

  it('plural word forms have the right number of variants', () => {
    const timeUnits = baseKeys.filter((k) => /^time\.(minute|hour|day|month|year)$/.test(k)) as Key[]
    expect(timeUnits).toHaveLength(5)
    for (const k of timeUnits) {
      expect(DICTIONARIES.uz[k].split('|'), k).toHaveLength(1)
      expect(DICTIONARIES.ru[k].split('|'), k).toHaveLength(3)
      expect(DICTIONARIES.en[k].split('|'), k).toHaveLength(2)
    }
  })

  it('uz and ru are actually translated (not copies of en)', () => {
    for (const lang of ['uz', 'ru'] as const) {
      const same = baseKeys.filter((k) => DICTIONARIES[lang][k as Key] === en[k as Key])
      // Only brand / format strings may be identical.
      expect(same.every((k) => ['app.name', 'source.nasa', 'nav.dashboard', 'common.demo'].includes(k)), `${lang}: ${same.join(', ')}`).toBe(true)
    }
  })
})

describe('English is the primary language', () => {
  it('is the default / fallback and comes first in the language switch (ENG · UZB · RUS)', () => {
    expect(DEFAULT_LANG).toBe('en')
    expect(LANGS).toEqual(['en', 'uz', 'ru'])
    expect(LANGS.map((l) => LANG_LABEL[l])).toEqual(['ENG', 'UZB', 'RUS'])
  })

  it('uses the agreed terminology', () => {
    expect(en['field.risk']).toBe('Drying risk')
    expect([en['risk.high'], en['risk.medium'], en['risk.low']]).toEqual(['High', 'Medium', 'Low'])
    expect([en['moisture.very_dry'], en['moisture.dry'], en['moisture.normal'], en['moisture.wet']]).toEqual(['Very dry', 'Dry', 'Adequate', 'Saturated'])
    expect(en['field.moisture']).toBe('Soil moisture')
    expect(en['field.sensors']).toBe('Active sensors')
    expect(en['field.lastAnalysis']).toBe('Last analysis')
    expect(en['form.irrigation']).toBe('Irrigation type')
    expect(en['form.water']).toBe('Water source')
    expect(en['form.plantingDate']).toBe('Planting date')
    expect(en['form.soil']).toBe('Soil type')
    expect(en['form.area']).toBe('Area (ha)')
    expect(en['fieldPage.agronom']).toBe('AI Agronomist')
    expect(en['settings.notify']).toBe('Notification frequency')
    expect([en['notify.daily3'], en['notify.2h'], en['notify.4h'], en['notify.8h'], en['notify.10h'], en['notify.weekly'], en['notify.monthly']]).toEqual([
      'Default (3 times a day: 08:00, 13:00, 19:00)',
      'Every 2 hours',
      'Every 4 hours',
      'Every 8 hours',
      'Every 10 hours',
      'Once a week',
      'Once a month',
    ])
  })

  it('has no Uzbek leftovers in English strings', () => {
    // Uzbek letters written with an apostrophe (o', g', sh' — any apostrophe form) and common Uzbek words.
    const uzbek = /\b(o|g)['ʻʼ‘’]|sh['ʻʼ‘’]|\b(dala|dalasi|yo['ʻ‘’]q|uchun|va|kerak|maydon|tuproq|ekin|sug['ʻ‘’]orish|qo['ʻ‘’]shish|sozlamalar|hudud|namlik|namligi|xavf|xavfi|qurish|datchik|datchiklar|tahlil|saqlash|ga|kun|soat|daqiqa|oldin|bilan|yoki|hozirgina)\b/i
    // The detector itself works:
    for (const sample of ["Yo'q", "Sug'orish turi", 'Dala nomi', 'Maydoni 3 ga', "O'rtacha", 'Qurish xavfi']) expect(uzbek.test(sample), sample).toBe(true)
    const offenders = baseKeys.filter((k) => uzbek.test(en[k as Key])).map((k) => `${k}: ${en[k as Key]}`)
    expect(offenders).toEqual([])
  })

  it('uses sentence case for buttons and labels', () => {
    const labels: Key[] = ['common.retry', 'login.demo', 'region.sendLocation', 'region.confirm', 'dashboard.addField', 'fieldPage.delete', 'fieldPage.deleteYes', 'settings.addField', 'form.crop', 'form.area', 'form.plantingDate', 'settings.notify']
    for (const k of labels) {
      const words = en[k].split(/\s+/).slice(1).filter((w) => /^[A-Za-z]/.test(w))
      // Only proper nouns / acronyms may be capitalised after the first word.
      expect(words.filter((w) => /^[A-Z][a-z]/.test(w) && !['Telegram', 'NASA', 'AI', 'Agronomist'].includes(w)), `${k}: ${en[k]}`).toEqual([])
    }
  })
})

describe('t() helper', () => {
  it('interpolates placeholders', () => {
    expect(interpolate('Salom, {name}!', { name: 'Ali' })).toBe('Salom, Ali!')
    expect(interpolate('{a} {b}', { a: 1 })).toBe('1 {b}')
    expect(translate('ru', 'agronom.remaining', { n: 27 })).toBe('Осталось вопросов сегодня: 27')
  })

  it('switches language globally', () => {
    setLang('en')
    expect(t('nav.settings')).toBe('Settings')
    setLang('ru')
    expect(t('nav.settings')).toBe('Настройки')
    setLang('uz')
    expect(t('nav.settings')).toBe('Sozlamalar')
    setLang('en')
  })

  it('normalises language codes (farmer.language / Telegram language_code)', () => {
    expect(toLang('ru-RU')).toBe('ru')
    expect(toLang('EN')).toBe('en')
    expect(toLang('uz')).toBe('uz')
    expect(toLang('de')).toBeNull()
    expect(toLang(null)).toBeNull()
  })

  it('picks Russian and English plural forms', () => {
    expect([1, 2, 5, 11, 21, 22, 25, 112].map((n) => pluralIndex('ru', n))).toEqual([0, 1, 2, 2, 0, 1, 2, 2])
    expect(plural('time.minute', 1, 'ru')).toBe('минуту')
    expect(plural('time.minute', 3, 'ru')).toBe('минуты')
    expect(plural('time.minute', 7, 'ru')).toBe('минут')
    expect(plural('time.hour', 1, 'en')).toBe('hour')
    expect(plural('time.hour', 2, 'en')).toBe('hours')
    expect(plural('time.hour', 2, 'uz')).toBe('soat')
  })
})

/** Guard against hard-coded UI text: JSX text nodes in components must come from t(). */
describe('no hard-coded UI text in components', () => {
  const root = join(__dirname, '..')
  const files: string[] = []
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name)
      if (statSync(p).isDirectory()) walk(p)
      else if (p.endsWith('.tsx')) files.push(p)
    }
  }
  walk(root)

  it('finds the component files', () => {
    expect(files.length).toBeGreaterThan(5)
  })

  it('has no literal words between JSX tags or in user-facing attributes', () => {
    const offenders: string[] = []
    for (const f of files) {
      const src = readFileSync(f, 'utf8')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '')
      // Text directly between tags: >  Some words  <
      // (not after "=>" arrows, e.g. "() => Promise<T>")
      for (const m of src.matchAll(/(?<![=-])>([^<>{}`]*)</g)) {
        const text = m[1].trim()
        // Skip TypeScript generics / code between "<…>" pairs (useState<T>(…) … useRef<).
        const looksLikeCode = /[()=;[\]]|=>|\b(const|return|let)\b|^:|\s\?$/.test(text)
        if (/[A-Za-zА-Яа-яЁёʻ']{2,}/.test(text) && !looksLikeCode) offenders.push(`${f}: ${text}`)
      }
      // placeholder / aria-label / title given as a plain string
      for (const m of src.matchAll(/\b(placeholder|aria-label|title|alt)="([^"]*)"/g)) {
        if (/[A-Za-zА-Яа-я]{2,}/.test(m[2])) offenders.push(`${f}: ${m[1]}="${m[2]}"`)
      }
    }
    expect(offenders).toEqual([])
  })
})
