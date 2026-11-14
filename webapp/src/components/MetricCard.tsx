import type { Metric } from '../api/types'
import { formatMetricParts, QUALITY_LABEL, SOURCE_ICON, SOURCE_NAME } from '../utils/format'
import { formatObserved } from '../utils/time'
import { Badge, NoData } from './ui'

/**
 * One dashboard metric (TG-6): value + unit, source badge, observed time
 * (relative + Tashkent), spatial resolution, quality flag, DEMO marker.
 * A null value is shown as "ma'lumot yo'q" — never a made-up number.
 */
export function MetricCard({ metric }: { metric: Metric }) {
  const value = formatMetricParts(metric)
  const q = metric.quality
  const flagged = q === 'suspect' || q === 'bad'
  const source = metric.source_label || (metric.source ? `${SOURCE_ICON[metric.source]} ${SOURCE_NAME[metric.source]}` : null)
  // The backend repeats "ma'lumot yo'q" in note for empty metrics — don't show it twice.
  const note = metric.note && !(value === null && metric.note.toLowerCase().includes("ma'lumot yo'q")) ? metric.note : null
  return (
    <div className={`metric ${flagged ? `metric--${q}` : ''} ${value === null ? 'metric--empty' : ''}`}>
      <div className="metric__label">
        <span>{metric.label_uz}</span>
        {metric.is_demo && (
          <span className="metric__demo" title="Demo ma'lumot — haqiqiy o'lchov emas">
            DEMO
          </span>
        )}
      </div>
      <div className="metric__value">
        {value ? (
          <>
            {value.main}
            {value.unit && <span className="metric__unit"> {value.unit}</span>}
          </>
        ) : (
          <NoData />
        )}
      </div>
      {source && (
        <div className="metric__source" title="Manba">
          {source}
        </div>
      )}
      {flagged && <Badge tone={q === 'bad' ? 'danger' : 'warning'}>⚠️ {QUALITY_LABEL[q]}</Badge>}
      {(metric.observed_at || value !== null) && <div className="metric__meta">🕒 {formatObserved(metric.observed_at)}</div>}
      {metric.resolution && <div className="metric__meta">📐 {metric.resolution}</div>}
      {note && <div className="metric__note">{note}</div>}
    </div>
  )
}
