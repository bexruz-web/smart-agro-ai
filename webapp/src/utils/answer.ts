/**
 * Turns an AI Agronom reply (plain text, possibly light markdown) into simple blocks:
 * paragraphs (line breaks kept), numbered steps and bullet lists. Long answers are split
 * into a short visible part and a "Batafsil" (more details) part.
 */

export interface ListItem {
  num: string
  text: string
}

export type Block =
  | { type: 'p'; text: string }
  | { type: 'ol'; items: ListItem[] }
  | { type: 'ul'; items: string[] }

export interface ParsedAnswer {
  main: Block[]
  more: Block[]
}

/** Answers longer than this (characters) are collapsed. */
export const LONG_ANSWER = 480
/** The visible part keeps at least this many characters before collapsing. */
const VISIBLE_MIN = 220

const NUMBERED = /^\s*(\d{1,2})[.)]\s+(.*)$/
const BULLET = /^\s*[-•*]\s+(.*)$/
/** An explicit "details" heading written by the model: "Batafsil:", "Подробнее:", "More details:". */
const MORE_MARKER = /^\s*(?:\*\*)?\s*(batafsil|подробнее|подробно|more details|details)\s*:?\s*(?:\*\*)?\s*:?\s*$/i

function cleanLine(line: string): string {
  return line.replace(/^\s*#{1,6}\s+/, '').replace(/\s+$/, '')
}

/** Splits text into blocks. Blank lines end a block; lines inside a paragraph keep their breaks. */
export function toBlocks(text: string): Block[] {
  const blocks: Block[] = []
  let cur: Block | null = null
  const flush = () => {
    if (cur) blocks.push(cur)
    cur = null
  }
  for (const raw of text.replace(/\r\n?/g, '\n').split('\n')) {
    const line = cleanLine(raw)
    if (!line.trim()) {
      flush()
      continue
    }
    const num = NUMBERED.exec(line)
    if (num) {
      if (cur?.type !== 'ol') {
        flush()
        cur = { type: 'ol', items: [] }
      }
      cur.items.push({ num: num[1], text: num[2].trim() })
      continue
    }
    const bullet = BULLET.exec(line)
    if (bullet) {
      if (cur?.type !== 'ul') {
        flush()
        cur = { type: 'ul', items: [] }
      }
      cur.items.push(bullet[1].trim())
      continue
    }
    const c = cur as Block | null
    if (c?.type === 'ol') c.items[c.items.length - 1].text += `\n${line.trim()}`
    else if (c?.type === 'ul') c.items[c.items.length - 1] += `\n${line.trim()}`
    else if (c?.type === 'p') c.text += `\n${line.trim()}`
    else {
      flush()
      cur = { type: 'p', text: line.trim() }
    }
  }
  flush()
  return blocks
}

function blockLength(b: Block): number {
  if (b.type === 'p') return b.text.length
  if (b.type === 'ol') return b.items.reduce((s, i) => s + i.text.length + 3, 0)
  return b.items.reduce((s, i) => s + i.length + 2, 0)
}

export function parseAnswer(text: string): ParsedAnswer {
  const src = (text ?? '').trim()
  const lines = src.replace(/\r\n?/g, '\n').split('\n')
  const markerAt = lines.findIndex((l, i) => i > 0 && MORE_MARKER.test(l))
  if (markerAt > 0) {
    const main = toBlocks(lines.slice(0, markerAt).join('\n'))
    const more = toBlocks(lines.slice(markerAt + 1).join('\n'))
    if (main.length && more.length) return { main, more }
  }

  const blocks = toBlocks(src)
  const total = blocks.reduce((s, b) => s + blockLength(b), 0)
  if (total <= LONG_ANSWER) return { main: blocks, more: [] }

  const main: Block[] = []
  const more: Block[] = []
  let used = 0
  for (const b of blocks) {
    if (more.length || (used >= VISIBLE_MIN && main.length)) {
      more.push(b)
      continue
    }
    const len = blockLength(b)
    if (used + len <= LONG_ANSWER || b.type === 'p') {
      main.push(b)
      used += len
      continue
    }
    // A long list: keep the first items visible, the rest go under "Batafsil" (numbers are kept).
    if (b.type === 'ol') {
      const head: ListItem[] = []
      const tail: ListItem[] = []
      for (const it of b.items) {
        if (!tail.length && (used < VISIBLE_MIN || !head.length)) {
          head.push(it)
          used += it.text.length + 3
        } else tail.push(it)
      }
      main.push({ type: 'ol', items: head })
      if (tail.length) more.push({ type: 'ol', items: tail })
    } else {
      const head: string[] = []
      const tail: string[] = []
      for (const it of b.items) {
        if (!tail.length && (used < VISIBLE_MIN || !head.length)) {
          head.push(it)
          used += it.length + 2
        } else tail.push(it)
      }
      main.push({ type: 'ul', items: head })
      if (tail.length) more.push({ type: 'ul', items: tail })
    }
  }
  return { main, more }
}

/** Splits "**bold**" markers into text / bold segments (no HTML is ever produced from the reply). */
export function inlineSegments(text: string): { text: string; bold: boolean }[] {
  const out: { text: string; bold: boolean }[] = []
  const re = /\*\*(.+?)\*\*/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ text: text.slice(last, m.index), bold: false })
    out.push({ text: m[1], bold: true })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ text: text.slice(last), bold: false })
  return out
}
