import { describe, expect, it } from 'vitest'
import {
  daysBetween,
  formatDateOnly,
  formatDateTime,
  formatObserved,
  formatRelative,
  formatTime,
  todayTashkent,
  weekdayShort,
} from './time'

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

describe('relative time (Uzbek)', () => {
  const now = new Date('2026-11-14T12:00:00Z')
  it('formats past times', () => {
    expect(formatRelative('2026-11-14T11:59:30Z', now)).toBe('hozirgina')
    expect(formatRelative('2026-11-14T11:55:00Z', now)).toBe('5 daqiqa oldin')
    expect(formatRelative('2026-11-14T09:00:00Z', now)).toBe('3 soat oldin')
    expect(formatRelative('2026-11-12T12:00:00Z', now)).toBe('2 kun oldin')
  })
  it('formats future times', () => {
    expect(formatRelative('2026-11-14T14:00:00Z', now)).toBe('2 soatdan keyin')
  })
  it('combines relative and absolute time', () => {
    expect(formatObserved('2026-11-14T09:00:00Z', now)).toBe('3 soat oldin · 14.11.2026 14:00')
    expect(formatObserved(null, now)).toBe("vaqt noma'lum")
  })
  it('shows daily (date-only) values without a clock time', () => {
    expect(formatObserved('2026-11-11', now)).toBe('3 kun oldin · 11-noyabr, 2026 (kunlik)')
    expect(formatObserved('2026-11-14', now)).toBe('bugun · 14-noyabr, 2026 (kunlik)')
    expect(formatObserved('2026-11-13', now)).toBe('kecha · 13-noyabr, 2026 (kunlik)')
  })
})

describe('calendar dates', () => {
  it('formats date-only strings without time-zone shifts', () => {
    expect(formatDateOnly('2026-11-15')).toBe('15-noyabr')
    expect(formatDateOnly('2026-01-01', true)).toBe('1-yanvar, 2026')
  })
  it('gives Uzbek weekday', () => {
    // 2026-11-14 is a Saturday
    expect(weekdayShort('2026-11-14')).toBe('Sh')
    expect(weekdayShort('2026-11-16')).toBe('Du')
  })
  it('counts days between dates', () => {
    expect(daysBetween('2026-10-15', '2026-11-14')).toBe(30)
  })
})
