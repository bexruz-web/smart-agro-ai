/**
 * AI Agronom for one field: dynamic suggested questions + this field's chat history
 * (GET /fields/{id}/agronom?lang=), POST /chat {message, field_id}.
 */
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router'
import { getAgronom, getField, sendChat } from '../api/endpoints'
import type { ChatMessage } from '../api/types'
import { AnswerText } from '../components/AnswerText'
import { IconSend } from '../components/icons'
import { ErrorBox, Loading, Page } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useI18n } from '../i18n'
import { formatDateTime } from '../utils/time'

export function AgronomPage() {
  const { id } = useParams()
  const fieldId = Number(id)
  const { t, lang } = useI18n()
  const field = useAsync(() => getField(fieldId), [fieldId])
  const info = useAsync(() => getAgronom(fieldId, lang), [fieldId, lang])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [remaining, setRemaining] = useState<number | null>(null)

  useEffect(() => {
    if (!info.data) return
    setMessages(info.data.history ?? [])
    setSuggestions(info.data.suggestions ?? [])
  }, [info.data])

  // Keep the newest message visible above the sticky composer: scroll the page to its very end
  // (instant for the loaded history, smooth for new messages).
  const firstScroll = useRef(true)
  useEffect(() => {
    if (!messages.length && !sending) return
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: firstScroll.current ? 'auto' : 'smooth' })
    firstScroll.current = false
  }, [messages.length, sending])

  const send = async (msg?: string) => {
    const message = (msg ?? text).trim()
    if (!message || sending) return
    setSending(true)
    setError(null)
    setMessages((m) => [...m, { role: 'user', content: message, created_at: new Date().toISOString() }])
    setText('')
    try {
      const r = await sendChat(message, fieldId)
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: r.reply, created_at: new Date().toISOString(), refused: r.refused, sources: r.sources },
      ])
      if (typeof r.remaining_today === 'number') setRemaining(r.remaining_today)
      // Suggestions depend on the conversation: refresh them quietly.
      getAgronom(fieldId, lang)
        .then((d) => setSuggestions(d.suggestions ?? []))
        .catch(() => undefined)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setText(message)
      setMessages((m) => m.slice(0, -1))
    } finally {
      setSending(false)
    }
  }

  const name = field.data?.name ?? '…'

  return (
    <Page
      title={t('agronom.title', { name })}
      subtitle={remaining !== null ? t('agronom.remaining', { n: remaining }) : undefined}
      back={`/fields/${fieldId}`}
      className="page--chat"
    >
      <div className="chat">
        <div className="chat__messages" aria-live="polite">
          {info.loading && !info.data && <Loading />}
          {info.error && <ErrorBox error={info.error} onRetry={info.reload} />}
          {info.data && messages.length === 0 && <div className="chat__empty">{t('agronom.empty')}</div>}
          {messages.map((m, i) => (
            <div key={i} className={`msg msg--${m.role} ${m.refused ? 'msg--refused' : ''}`}>
              <div className="msg__bubble">{m.role === 'assistant' ? <AnswerText text={m.content} /> : m.content}</div>
              <div className="msg__meta">
                {formatDateTime(m.created_at)}
                {m.sources && m.sources.length > 0 && <span> · {t('agronom.sources', { list: m.sources.join(', ') })}</span>}
              </div>
            </div>
          ))}
          {sending && (
            <div className="msg msg--assistant">
              <div className="msg__bubble msg__bubble--typing">{t('agronom.typing')}</div>
            </div>
          )}
        </div>

        <div className="chat__bottom">
          {suggestions.length > 0 && (
            <div className="chat__suggestions">
              {suggestions.map((s) => (
                <button key={s} type="button" className="btn btn--chip chat__chip" disabled={sending} onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
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
              rows={1}
              maxLength={2000}
              placeholder={t('agronom.placeholder')}
              aria-label={t('agronom.placeholder')}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
            />
            <button type="submit" className="btn btn--primary chat__send" disabled={sending || !text.trim()} aria-label={t('agronom.send')} title={t('agronom.send')}>
              <IconSend size={20} />
            </button>
          </form>
        </div>
      </div>
    </Page>
  )
}
