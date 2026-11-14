/** Field status UI shared by the Dashboard cards and the Field page. */
import { Link } from 'react-router'
import type { Field, FieldStatus } from '../api/types'
import { useI18n } from '../i18n'
import { fmtNum } from '../utils/format'
import {
  MOISTURE_CLASSES,
  MOISTURE_LABEL,
  RISK_EMOJI,
  RISK_LABEL,
  SOURCE_ICON,
  SOURCE_LABEL,
  STALE_MINUTES,
  moistureKey,
  offlineSensors,
  riskKey,
} from '../utils/status'
import { formatDateTime, formatRelative, minutesSince } from '../utils/time'
import { IconChevron } from './icons'
import { Badge, DemoBadge } from './ui'

export function RiskChip({ risk, large }: { risk: string | null | undefined; large?: boolean }) {
  const { t } = useI18n()
  const k = riskKey(risk)
  return (
    <span className={`risk-chip risk-chip--${k} ${large ? 'risk-chip--lg' : ''}`}>
      <span aria-hidden="true">{RISK_EMOJI[k]}</span> {t(RISK_LABEL[k])}
    </span>
  )
}

function MoistureValue({ status, withSource }: { status: FieldStatus | null | undefined; withSource?: boolean }) {
  const { t } = useI18n()
  const sm = status?.soil_moisture
  if (!sm || sm.value === null || sm.value === undefined) return <span className="no-data">{t('common.noData')}</span>
  const src = sm.source ?? ''
  const srcLabel = SOURCE_LABEL[src] ? t(SOURCE_LABEL[src]) : src
  const unit = sm.unit || '%'
  return (
    <>
      {unit === '%' ? `${fmtNum(sm.value, 0)}%` : fmtNum(sm.value, 1)}
      {unit !== '%' && <span className="metric__unit">{unit}</span>}
      {src && !withSource && (
        <span className="metric__src" title={srcLabel} aria-label={srcLabel}>
          {SOURCE_ICON[src] ?? ''}
        </span>
      )}
    </>
  )
}

/** The 5 card metrics after the name: area, soil moisture, active sensors, last analysis, drying risk. */
export function FieldMetrics({ field, detailed }: { field: Field; detailed?: boolean }) {
  const { t, lang } = useI18n()
  const s = field.status
  const total = s?.total_sensors ?? 0
  const active = s?.active_sensors ?? 0
  const offline = offlineSensors(s)
  const sm = s?.soil_moisture
  const age = minutesSince(sm?.observed_at)
  const stale = sm?.source === 'sensor' && age !== null && age > STALE_MINUTES
  const src = sm?.source ?? ''

  return (
    <div className={`metrics ${detailed ? 'metrics--detailed' : ''}`}>
      <div className="metric">
        <div className="metric__label">{t('field.area')}</div>
        <div className="metric__value">
          {fmtNum(field.area_ha, 2, lang)}
          <span className="metric__unit">{t('unit.ha')}</span>
        </div>
      </div>
      <div className="metric">
        <div className="metric__label">{t('field.moisture')}</div>
        <div className="metric__value">
          <MoistureValue status={s} withSource={detailed} />
        </div>
        {detailed && sm && sm.value !== null && (
          <div className="metric__meta">
            {SOURCE_ICON[src] ?? ''} {SOURCE_LABEL[src] ? t(SOURCE_LABEL[src]) : src}
            {sm.observed_at ? ` · ${formatRelative(sm.observed_at)}` : ''}
          </div>
        )}
        {detailed && stale && <Badge tone="warning">⚠️ {t('field.stale')}</Badge>}
      </div>
      <div className="metric">
        <div className="metric__label">{t('field.sensors')}</div>
        <div className={`metric__value ${offline > 0 ? 'metric__value--warn' : ''}`}>
          {active}
          <span className="metric__unit">/ {total}</span>
        </div>
        {detailed && offline > 0 && <Badge tone="warning">📴 {t('field.sensorsOffline', { n: offline })}</Badge>}
      </div>
      <div className="metric">
        <div className="metric__label">{t('field.lastAnalysis')}</div>
        <div className="metric__value metric__value--text" title={s?.last_analysis_at ? formatDateTime(s.last_analysis_at) : undefined}>
          {s?.last_analysis_at ? formatRelative(s.last_analysis_at) : <span className="no-data">{t('field.noAnalysis')}</span>}
        </div>
        {detailed && s?.last_analysis_at && <div className="metric__meta">{formatDateTime(s.last_analysis_at)}</div>}
      </div>
      <div className="metric metric--risk">
        <div className="metric__label">{t('field.risk')}</div>
        <RiskChip risk={s?.drying_risk} large={detailed} />
      </div>
    </div>
  )
}

/** Dashboard card: name + the 5 metrics; the whole card opens the Field page. */
export function FieldCard({ field }: { field: Field }) {
  const risk = riskKey(field.status?.drying_risk)
  return (
    <Link to={`/fields/${field.id}`} className={`field-card field-card--${risk}`}>
      <div className="field-card__head">
        <h3 className="field-card__name">
          {field.name} {field.is_demo && <DemoBadge />}
        </h3>
        <span className="field-card__chevron" aria-hidden="true">
          <IconChevron size={20} />
        </span>
      </div>
      <FieldMetrics field={field} />
    </Link>
  )
}

/** 4-class soil moisture legend (very dry · dry · normal · too wet) with the current class highlighted. */
export function MoistureLegend({ moistureClass }: { moistureClass: string | null | undefined }) {
  const { t } = useI18n()
  const current = moistureKey(moistureClass)
  return (
    <div className="legend">
      <div className="legend__bar" role="list" aria-label={t('moisture.title')}>
        {MOISTURE_CLASSES.map((c) => (
          <div
            key={c}
            role="listitem"
            aria-current={c === current ? 'true' : undefined}
            className={`legend__item legend__item--${c} ${c === current ? 'is-current' : ''}`}
          >
            <span className="legend__swatch">{c === current ? '✓' : ''}</span>
            <span className="legend__label">{t(MOISTURE_LABEL[c])}</span>
          </div>
        ))}
      </div>
      {current === 'unknown' && <div className="muted small">{t('moisture.unknown')}</div>}
    </div>
  )
}
