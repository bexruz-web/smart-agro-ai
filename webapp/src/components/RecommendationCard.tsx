import { useState, type ReactNode } from 'react'
import { sendFeedback } from '../api/endpoints'
import type { Evidence, FeedbackAction, Recommendation } from '../api/types'
import { haptic } from '../telegram'
import { CATEGORY_LABEL, fmtNum } from '../utils/format'
import { formatDateTime, formatObserved } from '../utils/time'
import { Badge, BulletList, ConfidenceBadge, NoData, SeverityBadge } from './ui'

const FEEDBACK: { action: FeedbackAction; label: string }[] = [
  { action: 'done', label: '✅ Bajardim' },
  { action: 'later', label: '⏰ Keyinroq' },
  { action: 'rejected', label: '❌ Kerak emas' },
  { action: 'useful', label: '👍' },
  { action: 'not_useful', label: '👎' },
]

const STATUS_LABEL: Record<string, string> = {
  done: '✅ Bajarilgan',
  later: '⏰ Keyinroq',
  rejected: '❌ Kerak emas',
}

function evidenceValue(e: Evidence) {
  if (e.value === null || e.value === undefined) return <NoData />
  if (typeof e.value === 'boolean') return e.value ? 'Ha' : "Yo'q"
  if (typeof e.value === 'number') return `${fmtNum(e.value, 2)}${e.unit ? ` ${e.unit}` : ''}`
  return `${e.value}${e.unit ? ` ${e.unit}` : ''}`
}

function Part({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <div className="rec__part">
      <div className="rec__part-title">
        <span className="rec__num">{n}</span> {title}
      </div>
      <div className="rec__part-body">{children}</div>
    </div>
  )
}

/** DSS-2: all 7 parts + confidence, facts vs assumptions, AI marker and FB-1 buttons. */
export function RecommendationCard({ rec }: { rec: Recommendation }) {
  const [status, setStatus] = useState(rec.status)
  const [sent, setSent] = useState<FeedbackAction[]>([])
  const [busy, setBusy] = useState<FeedbackAction | null>(null)
  const [error, setError] = useState<string | null>(null)

  const feedback = async (action: FeedbackAction) => {
    setBusy(action)
    setError(null)
    try {
      await sendFeedback(rec.id, action)
      setSent((s) => [...s.filter((x) => x !== action), action])
      if (action === 'done' || action === 'later' || action === 'rejected') setStatus(action)
      haptic('success')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <article className={`rec rec--${rec.severity}`}>
      <header className="rec__head">
        <SeverityBadge value={rec.severity} />
        <Badge>{CATEGORY_LABEL[rec.category] ?? rec.category}</Badge>
        {rec.ai_explained && (
          <Badge tone="accent" title="Matnni AI tushuntirgan; raqamlar deterministik hisobdan">
            🤖 AI izohi
          </Badge>
        )}
        {status !== 'new' && <Badge tone="neutral">{STATUS_LABEL[status] ?? status}</Badge>}
      </header>
      {rec.title_uz && <h3 className="rec__title">{rec.title_uz}</h3>}
      <div className="muted small">{formatDateTime(rec.created_at)}</div>

      <Part n={1} title="Muammo">
        {rec.problem}
      </Part>
      <Part n={2} title="Sabab">
        {rec.cause}
      </Part>
      <Part n={3} title="Dalillar">
        {rec.evidence.length ? (
          <ul className="evidence">
            {rec.evidence.map((e, i) => (
              <li key={`${e.fact_id}-${i}`}>
                <div>
                  <strong>{e.label_uz}:</strong> {evidenceValue(e)}
                </div>
                <div className="muted small">
                  {e.source_label} · {formatObserved(e.observed_at)}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <span className="muted">Dalil keltirilmagan</span>
        )}
      </Part>
      <Part n={4} title="Harakat">
        <strong>{rec.action}</strong>
      </Part>
      <Part n={5} title="Vaqt">
        {rec.timing}
      </Part>
      <Part n={6} title="Kutilayotgan natija">
        {rec.expected_outcome}
      </Part>
      <Part n={7} title="Xavf va noaniqliklar">
        {rec.risks}
      </Part>

      <div className="rec__confidence">
        <ConfidenceBadge value={rec.confidence} />
        {rec.confidence_reason && <span className="muted small">{rec.confidence_reason}</span>}
      </div>

      <div className="rec__lists">
        <div>
          <div className="rec__list-title">Faktlar</div>
          <BulletList items={rec.facts} empty="—" />
        </div>
        <div>
          <div className="rec__list-title">Taxminlar</div>
          <BulletList items={rec.assumptions} empty="—" />
        </div>
      </div>

      <div className="feedback" role="group" aria-label="Fikr bildirish">
        {FEEDBACK.map((f) => (
          <button
            key={f.action}
            type="button"
            className={`btn btn--chip ${sent.includes(f.action) || status === f.action ? 'is-active' : ''}`}
            disabled={busy !== null}
            onClick={() => feedback(f.action)}
          >
            {busy === f.action ? '…' : f.label}
          </button>
        ))}
      </div>
      {sent.length > 0 && !error && <div className="muted small">Rahmat! Javobingiz saqlandi.</div>}
      {error && <div className="form-row__error">{error}</div>}
    </article>
  )
}
