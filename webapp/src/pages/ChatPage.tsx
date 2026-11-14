/** AI agronom — POST /chat, GET /chat/history (CHAT-1..4). */
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { getChatHistory, getFields, sendChat } from '../api/endpoints'
import type { ChatMessage } from '../api/types'
import { ErrorBox, Loading, Page } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { formatDateTime } from '../utils/time'

const SUGGESTIONS = [
  'Bugun sug\'orish kerakmi?',
  'Hosildorlik prognozini tushuntiring',
  "Keyingi mavsumda nima ekish yaxshi?",
  "Tuproq sho'rlanishini qanday kamaytirish mumkin?",
]

export function ChatPage() {
  const [params, setParams] = useSearchParams()
  const fieldParam = params.get('field')
  const [fieldId, setFieldId] = useState<number | null>(fieldParam ? Number(fieldParam) : null)
  const fields = useAsync(getFields, [])
  const history = useAsync(getChatHistory, [])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [remaining, setRemaining] = useState<number | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (history.data) setMessages(history.data)
  }, [history.data])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, sending])

  const selectField = (v: string) => {
    const idNum = v ? Number(v) : null
    setFieldId(idNum)
    setParams(idNum ? { field: String(idNum) } : {}, { replace: true })
  }

  const send = async (msg?: string) => {
    const message = (msg ?? text).trim()
    if (!message || sending) return
    setSending(true)
    setError(null)
    const now = new Date().toISOString()
    setMessages((m) => [...m, { role: 'user', content: message, created_at: now }])
    setText('')
    try {
      const r = await sendChat(message, fieldId)
      setMessages((m) => [...m, { role: 'assistant', content: r.reply, created_at: new Date().toISOString(), refused: r.refused, sources: r.sources }])
      if (r.remaining_today !== null && r.remaining_today !== undefined) setRemaining(r.remaining_today)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setText(message)
      setMessages((m) => m.slice(0, -1))
    } finally {
      setSending(false)
    }
  }

  return (
    <Page title="AI agronom" subtitle="Faqat qishloq xo'jaligi bo'yicha savollar">
      <div className="chat">
        <div className="chat__toolbar">
          <select className="input" aria-label="Dala" value={fieldId ?? ''} onChange={(e) => selectField(e.target.value)}>
            <option value="">Umumiy savol (dala tanlanmagan)</option>
            {(fields.data ?? []).map((f) => (
              <option key={f.id} value={f.id}>
                🌾 {f.name}
              </option>
            ))}
          </select>
          {remaining !== null && <div className="muted small">Bugun qolgan savollar: {remaining}</div>}
        </div>

        <div className="chat__messages" aria-live="polite">
          {history.loading && <Loading />}
          {history.error && <ErrorBox error={history.error} onRetry={history.reload} />}
          {!history.loading && messages.length === 0 && (
            <div className="chat__empty">
              <p>Salom! Men Smart Agro AI agronomik yordamchisiman. Dala ma'lumotlaringiz asosida javob beraman — ma'lumot bo'lmasa, ochiq aytaman.</p>
              <div className="chips">
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className="btn btn--chip" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg msg--${m.role} ${m.refused ? 'msg--refused' : ''}`}>
              <div className="msg__bubble">{m.content}</div>
              <div className="msg__meta">
                {formatDateTime(m.created_at)}
                {m.sources && m.sources.length > 0 && <span> · Manbalar: {m.sources.join(', ')}</span>}
              </div>
            </div>
          ))}
          {sending && (
            <div className="msg msg--assistant">
              <div className="msg__bubble msg__bubble--typing">AI agronom yozmoqda…</div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {error && <ErrorBox error={error} />}
        <form
          className="chat__composer"
          onSubmit={(e) => {
            e.preventDefault()
            send()
          }}
        >
          <textarea
            className="input"
            rows={2}
            maxLength={2000}
            placeholder="Savolingizni yozing…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
          />
          <button type="submit" className="btn btn--primary" disabled={sending || !text.trim()}>
            Yuborish
          </button>
        </form>
      </div>
    </Page>
  )
}
