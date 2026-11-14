import { describe, expect, it } from 'vitest'
import { decimalToInput, fmtNum, parseDecimal } from './format'

describe('fmtNum follows the UI language', () => {
  it('uses a decimal comma in uz / ru and a dot in en', () => {
    expect(fmtNum(76.23, 2, 'uz')).toBe('76,23')
    expect(fmtNum(76.23, 2, 'ru')).toBe('76,23')
    expect(fmtNum(76.23, 2, 'en')).toBe('76.23')
  })

  it('groups thousands and drops trailing zeros', () => {
    expect(fmtNum(5000, 0, 'uz')).toBe('5 000')
    expect(fmtNum(5000, 0, 'en')).toBe('5,000')
    expect(fmtNum(3.1, 2, 'uz')).toBe('3,1')
    expect(fmtNum(3, 2, 'en')).toBe('3')
    expect(fmtNum(0.05, 2, 'uz')).toBe('0,05')
  })

  it('rounds half away from zero and handles missing values', () => {
    expect(fmtNum(2.15, 1, 'en')).toBe('2.2')
    expect(fmtNum(31.6, 0, 'en')).toBe('32')
    expect(fmtNum(null)).toBe('—')
    expect(fmtNum(Number.NaN)).toBe('—')
  })
})

describe('parseDecimal accepts a decimal comma', () => {
  it('parses farmer input', () => {
    expect(parseDecimal('76,23')).toBe(76.23)
    expect(parseDecimal('76.23')).toBe(76.23)
    expect(parseDecimal(' 2,5 ')).toBe(2.5)
    expect(parseDecimal('1 250,5')).toBe(1250.5)
    expect(parseDecimal('3')).toBe(3)
    expect(parseDecimal(',5')).toBe(0.5)
  })

  it('rejects anything else', () => {
    expect(parseDecimal('')).toBeNull()
    expect(parseDecimal('abc')).toBeNull()
    expect(parseDecimal('1,2,3')).toBeNull()
    expect(parseDecimal('-4')).toBeNull()
    expect(parseDecimal('5 ga')).toBeNull()
  })

  it('writes numbers back for the input', () => {
    expect(decimalToInput(76.23, 'uz')).toBe('76,23')
    expect(decimalToInput(76.23, 'en')).toBe('76.23')
    expect(decimalToInput(null, 'uz')).toBe('')
  })
})
