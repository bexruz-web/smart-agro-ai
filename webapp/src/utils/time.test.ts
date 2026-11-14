import { describe, expect, it } from 'vitest'
import { formatDateTime, formatRelative, formatTime, isValidDateOnly, minutesSince, todayTashkent } from './time'

describe('Asia/Tashkent formatting', () => {
  it('converts UTC to Tashkent (UTC+5)', () => {
    expect(formatDateTime('2026-11-14T09:00:00Z')).toBe('14.11.2026 14:00')
    expect(formatTime('2026-11-14T09:05:00Z')).toBe('14:05')
  })

  it('rolls over the date after 19:00 UTC', () => {
    expect(formatDateTime('2026-11-14T19:30:00Z')).toBe('15.11.2026 00:30')
    expect(todayTashkent(new Date('2026-12-31T19:00:00Z'))).toBe('2027-01-01')
  })

  it('handles offsets in the input string', () => {
    expect(formatDateTime('2026-11-14T14:00:00+05:00')).toBe('14.11.2026 14:00')
  })

  it('returns a dash for empty or invalid input', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('not a date')).toBe('—')
  })
})

describe('relative time in 3 languages', () => {
  const now = new Date('2026-11-14T12:00:00Z')

  it('uz', () => {
    expect(formatRelative('2026-11-14T11:59:30Z', now, 'uz')).toBe('hozirgina')
    expect(formatRelative('2026-11-14T11:55:00Z', now, 'uz')).toBe('5 daqiqa oldin')
    expect(formatRelative('2026-11-14T09:00:00Z', now, 'uz')).toBe('3 soat oldin')
    expect(formatRelative('2026-11-12T12:00:00Z', now, 'uz')).toBe('2 kun oldin')
    expect(formatRelative('2026-11-14T14:00:00Z', now, 'uz')).toBe('2 soatdan keyin')
  })

  it('ru (with plural forms)', () => {
    expect(formatRelative('2026-11-14T11:59:30Z', now, 'ru')).toBe('только что')
    expect(formatRelative('2026-11-14T11:59:00Z', now, 'ru')).toBe('1 минуту назад')
    expect(formatRelative('2026-11-14T11:57:00Z', now, 'ru')).toBe('3 минуты назад')
    expect(formatRelative('2026-11-14T11:55:00Z', now, 'ru')).toBe('5 минут назад')
    expect(formatRelative('2026-11-13T11:00:00Z', now, 'ru')).toBe('1 день назад')
    expect(formatRelative('2026-11-14T14:00:00Z', now, 'ru')).toBe('через 2 часа')
  })

  it('en', () => {
    expect(formatRelative('2026-11-14T11:59:30Z', now, 'en')).toBe('just now')
    expect(formatRelative('2026-11-14T11:59:00Z', now, 'en')).toBe('1 minute ago')
    expect(formatRelative('2026-11-14T11:55:00Z', now, 'en')).toBe('5 minutes ago')
    expect(formatRelative('2026-10-10T12:00:00Z', now, 'en')).toBe('1 month ago')
  })

  it('empty input', () => {
    expect(formatRelative(null, now, 'uz')).toBe('—')
  })
})

describe('dates', () => {
  it('validates calendar dates', () => {
    expect(isValidDateOnly('2026-10-12')).toBe(true)
    expect(isValidDateOnly('2026-02-30')).toBe(false)
    expect(isValidDateOnly('12.10.2026')).toBe(false)
    expect(isValidDateOnly('')).toBe(false)
  })

  it('computes minutes since an instant', () => {
    const now = new Date('2026-11-14T12:00:00Z')
    expect(minutesSince('2026-11-14T11:30:00Z', now)).toBe(30)
    expect(minutesSince(null, now)).toBeNull()
  })
})
