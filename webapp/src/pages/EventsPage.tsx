/** Ishlar jurnali — GET/POST /fields/{id}/events (irrigation, fertilizer, tillage, pesticide, other). */
import { useState } from 'react'
import { useParams } from 'react-router'
import { addEvent, getEvents } from '../api/endpoints'
import type { EventType, FieldEvent } from '../api/types'
import { Card, Empty, ErrorBox, FormRow, Loading, Page } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { haptic } from '../telegram'
import { eventTypeInfo, EVENT_TYPES, fmtNum } from '../utils/format'
import { parseCoordinate } from '../utils/geo'
import { formatDateOnly, todayTashkent, weekdayShort } from '../utils/time'

/** Who created the journal entry (farmer entries need no label). */
const EVENT_SOURCE: Record<string, string> = {
  recommendation: 'tavsiya asosida',
  bot: 'bot orqali',
  demo: 'demo',
  sensor: 'sensor',
  system: 'tizim',
}

function AddEventForm({ fieldId, onAdded }: { fieldId: number; onAdded: (e: FieldEvent) => void }) {
  const [type, setType] = useState<EventType>('irrigation')
  const [date, setDate] = useState(todayTashkent())
  const [amountText, setAmountText] = useState('')
  const [unit, setUnit] = useState(eventTypeInfo('irrigation').units[0])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const amount = amountText.trim() ? parseCoordinate(amountText) : null
  const amountErr = amountText.trim() && (amount === null || amount < 0) ? 'Musbat son kiriting' : null

  const changeType = (t: EventType) => {
    setType(t)
    setUnit(eventTypeInfo(t).units[0])
  }

  const submit = async () => {
    if (amountErr || !date) return
    setBusy(true)
    setError(null)
    try {
      const body: FieldEvent = { type, date, amount, unit: amount !== null ? unit || null : null, note: note.trim() || null }
      const saved = await addEvent(fieldId, body)
      onAdded(saved ?? body)
      setAmountText('')
      setNote('')
      haptic('success')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  const units = eventTypeInfo(type).units
  return (
    <Card title="Ish qo'shish">
      <FormRow label="Ish turi">
        <div className="chips">
          {EVENT_TYPES.map((t) => (
            <button key={t.value} type="button" className={`btn btn--chip ${type === t.value ? 'is-active' : ''}`} onClick={() => changeType(t.value)}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      </FormRow>
      <FormRow label="Sana" htmlFor="e-date">
        <input id="e-date" type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
      </FormRow>
      <FormRow label="Miqdor (ixtiyoriy)" error={amountErr} hint={type === 'irrigation' ? '1 mm = 10 m³/ga' : undefined} htmlFor="e-amount">
        <div className="input-group">
          <input id="e-amount" className="input" inputMode="decimal" placeholder="Masalan: 40" value={amountText} onChange={(e) => setAmountText(e.target.value)} />
          <select className="input input--unit" aria-label="Birlik" value={unit} onChange={(e) => setUnit(e.target.value)}>
            {units.map((u) => (
              <option key={u} value={u}>
                {u || '—'}
              </option>
            ))}
          </select>
        </div>
      </FormRow>
      <FormRow label="Izoh" htmlFor="e-note">
        <textarea id="e-note" className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Masalan: egatlab sug'orildi" />
      </FormRow>
      {error && <ErrorBox error={error} />}
      <button type="button" className="btn btn--primary btn--block" onClick={submit} disabled={busy || !!amountErr || !date}>
        {busy ? 'Saqlanmoqda…' : 'Saqlash'}
      </button>
    </Card>
  )
}

export function EventsPage() {
  const { id } = useParams()
  const fieldId = Number(id)
  const events = useAsync(() => getEvents(fieldId), [fieldId])
  const list = [...(events.data ?? [])].sort((a, b) => b.date.localeCompare(a.date) || (b.id ?? 0) - (a.id ?? 0))

  return (
    <Page title="Ishlar jurnali" back={`/fields/${fieldId}`}>
      <AddEventForm fieldId={fieldId} onAdded={(e) => events.setData((prev) => [e, ...(prev ?? [])])} />
      {events.loading && !events.data && <Loading />}
      {events.error && <ErrorBox error={events.error} onRetry={events.reload} />}
      {events.data && !list.length && <Empty>Hali ish qayd etilmagan</Empty>}
      {list.length > 0 && (
        <ul className="timeline">
          {list.map((e, i) => {
            const t = eventTypeInfo(e.type)
            return (
              <li key={e.id ?? `new-${i}`} className="timeline__item">
                <div className="timeline__icon" aria-hidden="true">
                  {t.icon}
                </div>
                <div className="timeline__body">
                  <div>
                    <strong>{t.label}</strong>
                    {e.amount !== null && e.amount !== undefined && (
                      <span>
                        {' '}
                        · {fmtNum(e.amount, 1)} {e.unit ?? ''}
                        {e.type === 'irrigation' && e.unit === 'mm' && ` (${fmtNum(e.amount * 10, 0)} m³/ga)`}
                      </span>
                    )}
                  </div>
                  <div className="muted small">
                    {formatDateOnly(e.date, true)} · {weekdayShort(e.date)}
                    {e.source && e.source !== 'farmer' && ` · ${EVENT_SOURCE[e.source] ?? e.source}`}
                  </div>
                  {e.note && <div>{e.note}</div>}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Page>
  )
}
