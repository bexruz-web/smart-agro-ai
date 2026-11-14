import { describe, expect, it } from 'vitest'
import { LONG_ANSWER, inlineSegments, parseAnswer, toBlocks } from './answer'

describe('AI answer rendering', () => {
  it('keeps line breaks inside a paragraph and splits on blank lines', () => {
    expect(toBlocks('Salom!\nBugun sug‘orish shart emas.\n\nErtaga yomg‘ir.')).toEqual([
      { type: 'p', text: 'Salom!\nBugun sug‘orish shart emas.' },
      { type: 'p', text: 'Ertaga yomg‘ir.' },
    ])
  })

  it('recognises numbered steps (1. / 2)) and bullets', () => {
    const blocks = toBlocks('Qadamlar:\n1. Tuproqni tekshiring\n2) Sug‘oring 20 mm\n   kechqurun\n- Eslatma')
    expect(blocks).toEqual([
      { type: 'p', text: 'Qadamlar:' },
      {
        type: 'ol',
        items: [
          { num: '1', text: 'Tuproqni tekshiring' },
          { num: '2', text: 'Sug‘oring 20 mm\nkechqurun' },
        ],
      },
      { type: 'ul', items: ['Eslatma'] },
    ])
  })

  it('does not collapse short answers', () => {
    const r = parseAnswer('Bugun sug‘orish kerak emas.')
    expect(r.more).toEqual([])
    expect(r.main).toHaveLength(1)
  })

  it('collapses long answers under "Batafsil"', () => {
    const para = 'Tuproq namligi me’yorida, ertaga yomg‘ir kutilmoqda. '.repeat(6)
    const text = `${para}\n\n${para}\n\n${para}`
    expect(text.length).toBeGreaterThan(LONG_ANSWER)
    const r = parseAnswer(text)
    expect(r.main.length).toBeGreaterThan(0)
    expect(r.more.length).toBeGreaterThan(0)
  })

  it('splits a long numbered list but keeps the original numbers', () => {
    const steps = Array.from({ length: 8 }, (_, i) => `${i + 1}. ${'Bu qadamda dalani diqqat bilan ko‘zdan kechiring va qayd eting. '.repeat(2)}`).join('\n')
    const r = parseAnswer(steps)
    const head = r.main[0]
    const tail = r.more[0]
    expect(head.type).toBe('ol')
    expect(tail.type).toBe('ol')
    if (head.type === 'ol' && tail.type === 'ol') {
      expect(head.items[0].num).toBe('1')
      expect(tail.items[0].num).toBe(String(head.items.length + 1))
      expect(head.items.length + tail.items.length).toBe(8)
    }
  })

  it('uses an explicit "Batafsil:" / "Подробнее:" heading from the model', () => {
    const r = parseAnswer('1. Sug‘oring\n2. Kuzating\n\nBatafsil:\nFAO-56 bo‘yicha hisob…')
    expect(r.main).toEqual([{ type: 'ol', items: [{ num: '1', text: 'Sug‘oring' }, { num: '2', text: 'Kuzating' }] }])
    expect(r.more).toEqual([{ type: 'p', text: 'FAO-56 bo‘yicha hisob…' }])
    expect(parseAnswer('Коротко.\n**Подробнее:**\nДлинный текст').more).toEqual([{ type: 'p', text: 'Длинный текст' }])
  })

  it('turns **bold** into segments without producing HTML', () => {
    expect(inlineSegments('Azot: **N 60 kg/ga** (laboratoriya tahlili bilan)')).toEqual([
      { text: 'Azot: ', bold: false },
      { text: 'N 60 kg/ga', bold: true },
      { text: ' (laboratoriya tahlili bilan)', bold: false },
    ])
    expect(inlineSegments('<b>x</b>')).toEqual([{ text: '<b>x</b>', bold: false }])
  })
})
