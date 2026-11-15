/**
 * Field page: map zoomed to the field, soil-moisture state with the 4-class legend,
 * the card metrics, "AI Agronom" / "Tahrirlash" and delete (in-page confirmation).
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { deleteField, getField, getFieldDashboard, getFields } from '../api/endpoints'
import type { Field } from '../api/types'
import type { MessageKey } from '../i18n'
import { FieldMetrics, MoistureLegend } from '../components/field'
import { IconChat, IconEdit, IconTrash } from '../components/icons'
import { Badge, Card, DemoBadge, ErrorBox, Loading, Page } from '../components/ui'
import { FIELD_ZOOM } from '../config'
import { useAsync } from '../hooks/useAsync'
import { useI18n } from '../i18n'
import { MapView } from '../map/MapView'
import type { MapController } from '../map/types'
import { haptic } from '../telegram'
import { fmtNum } from '../utils/format'
import { fieldPoint, fromGeoJsonPolygon } from '../utils/geo'
import { MOISTURE_LABEL, moistureKey, riskColor } from '../utils/status'
import { formatDay, formatRelative } from '../utils/time'

const METRIC_ICONS: Record<string, string> = {
  soil_moisture: '💧',
  soil_temp: '🌱',
  air_temp: '🌡️',
  air_humidity: '💨',
  light: '💡',
  rain_detected: '🌧️',
  precip_probability_today: '☔',
  precip_today: '🌧️',
  snowfall_today: '❄️',
  wind_speed: '🌬️',
  solar_radiation: '☀️',
  et0_today: '🔄',
  nasa_t2m: '🛰️',
  nasa_precip_7d: '🛰️',
  nasa_solar: '🛰️',
  nasa_soil_wetness_top: '🛰️',
  nasa_soil_wetness_root: '🛰️',
}

/** Alert severity (API: critical · warning · info) → card style, badge tone and label. */
const SEV: Record<string, { cls: string; tone: 'danger' | 'warning' | 'info'; label: MessageKey }> = {
  critical: { cls: 'rec-item--high', tone: 'danger', label: 'sev.critical' },
  warning: { cls: 'rec-item--medium', tone: 'warning', label: 'sev.warning' },
  info: { cls: '', tone: 'info', label: 'sev.info' },
}

const CONF_LABEL: Record<string, MessageKey> = { low: 'conf.low', medium: 'conf.medium', high: 'conf.high' }

/** GET /fields/{id}; if that response has no `status`, take it from the GET /fields list. */
async function loadField(id: number): Promise<Field> {
  const f = await getField(id)
  if (f.status === undefined) {
    const match = (await getFields().catch(() => [] as Field[])).find((x) => x.id === id)
    if (match?.status !== undefined) return { ...f, status: match.status }
  }
  return f
}

function FieldMap({ field }: { field: Field }) {
  const [map, setMap] = useState<MapController | null>(null)
  const onReady = useCallback((m: MapController) => setMap(m), [])
  useEffect(() => {
    if (!map) return
    const color = riskColor(field.status?.drying_risk)
    const ring = fromGeoJsonPolygon(field.geometry)
    const p = fieldPoint(field)
    map.setPolygons(ring.length >= 3 ? [{ id: 'field', points: ring, color }] : [])
    map.setMarkers(p ? [{ id: 'field', position: p, kind: 'field', color }] : [])
    if (ring.length >= 3) map.fitTo(ring, 17)
    else if (p) map.setView(p, FIELD_ZOOM)
  }, [map, field])
  const center = fieldPoint(field)
  if (!center) return null
  return <MapView className="map--field" options={{ center, zoom: FIELD_ZOOM, interactive: false }} onReady={onReady} />
}

function DeleteField({ field }: { field: Field }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [asking, setAsking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const remove = async () => {
    setBusy(true)
    setError(null)
    try {
      await deleteField(field.id)
      haptic('success')
      navigate('/', { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
      setBusy(false)
    }
  }

  if (!asking) {
    return (
      <button type="button" className="btn btn--danger-ghost btn--block" onClick={() => setAsking(true)}>
        <IconTrash size={18} /> {t('fieldPage.delete')}
      </button>
    )
  }
  return (
    <div className="confirm" role="alertdialog" aria-labelledby="del-q">
      <p id="del-q" className="confirm__text">
        {t('fieldPage.deleteConfirm', { name: field.name })}
      </p>
      {error && <ErrorBox error={error} />}
      <div className="btn-row">
        <button type="button" className="btn btn--danger" onClick={remove} disabled={busy}>
          {busy ? t('fieldPage.deleting') : t('fieldPage.deleteYes')}
        </button>
        <button type="button" className="btn btn--secondary" onClick={() => setAsking(false)} disabled={busy}>
          {t('common.cancel')}
        </button>
      </div>
    </div>
  )
}

export function FieldPage() {
  const { id } = useParams()
  const fieldId = Number(id)
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const field = useAsync(() => loadField(fieldId), [fieldId])
  const dashboard = useAsync(() => getFieldDashboard(fieldId, lang), [fieldId, lang])
  const f = field.data
  const dash = dashboard.data

  if (!f) {
    return (
      <Page title="…" back="/">
        {field.loading && <Loading />}
        {field.error && <ErrorBox error={field.error} onRetry={field.reload} />}
      </Page>
    )
  }

  const s = f.status
  const mClass = moistureKey(s?.moisture_class)
  const sm = s?.soil_moisture

  // Filter metrics that have values or are core parameters
  const metricsList = dash?.metrics?.filter((m) => m.value !== null && m.value !== undefined) ?? []

  return (
    <Page title={f.name} subtitle={f.is_demo ? <DemoBadge /> : undefined} back="/">
      <FieldMap field={f} />

      <Card title={t('moisture.title')} className="moisture-card">
        <div className="moisture-card__now">
          {sm && sm.value !== null && sm.value !== undefined ? (
            <span className="moisture-card__value">{`${fmtNum(sm.value, 0)}${sm.unit || '%'}`}</span>
          ) : (
            mClass === 'unknown' && <span className="moisture-card__value">—</span>
          )}
          {mClass !== 'unknown' && <span className={`moisture-card__class moisture-card__class--${mClass}`}>{t(MOISTURE_LABEL[mClass])}</span>}
        </div>
        <MoistureLegend moistureClass={s?.moisture_class} />
      </Card>

      <Card>
        <FieldMetrics field={f} detailed />
      </Card>

      <div className="action-row">
        <button type="button" className="btn btn--primary btn--lg" onClick={() => navigate(`/fields/${f.id}/agronom`)}>
          <IconChat size={20} /> {t('fieldPage.agronom')}
        </button>
        <button type="button" className="btn btn--secondary btn--lg" onClick={() => navigate(`/fields/${f.id}/edit`)}>
          <IconEdit size={20} /> {t('fieldPage.edit')}
        </button>
      </div>

      {/* Sensor & Climate Data Grid */}
      {metricsList.length > 0 && (
        <Card title={t('field.metricsTitle')}>
          <div className="sensor-grid">
            {metricsList.map((m) => (
              <div key={m.key} className="sensor-card">
                <div className="sensor-card__head">
                  <span className="sensor-card__label" title={m.label || m.label_uz}>
                    {METRIC_ICONS[m.key] ?? '📊'} {m.label || m.label_uz}
                  </span>
                  {m.source_label && <span className="sensor-card__src">{m.source_label}</span>}
                </div>
                <div className="sensor-card__val">
                  {m.value_text ?? (typeof m.value === 'number' ? fmtNum(m.value, Number.isInteger(m.value) ? 0 : 1, lang) : '—')}
                  {!m.value_text && m.unit && <span className="sensor-card__unit">{m.unit}</span>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Crop Status & Yield Forecast */}
      {(dash?.crop_status || dash?.yield_forecast) && (
        <Card title={t('field.cropTitle')}>
          {dash.crop_status && (
            <div className="metrics">
              <div className="metric">
                <div className="metric__label">{t('form.crop')}</div>
                <div className="metric__value metric__value--text">
                  {dash.crop_status.crop_name || dash.crop_status.crop_name_uz || dash.crop_status.crop}
                </div>
              </div>
              <div className="metric">
                <div className="metric__label">{t('field.cropStage')}</div>
                <div className="metric__value metric__value--text">
                  {dash.crop_status.stage_name || dash.crop_status.stage_uz || '—'}
                </div>
              </div>
              {dash.crop_status.days_since_planting !== null && (
                <div className="metric">
                  <div className="metric__label">{t('field.plantedDays')}</div>
                  <div className="metric__value">
                    {dash.crop_status.days_since_planting} <span className="metric__unit">{t('field.daysUnit')}</span>
                  </div>
                </div>
              )}
              {dash.crop_status.gdd !== null && (
                <div className="metric">
                  <div className="metric__label">{t('field.gdd')}</div>
                  <div className="metric__value">
                    {fmtNum(dash.crop_status.gdd, 0, lang)} <span className="metric__unit">{t('unit.gdd')}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {dash.yield_forecast && (
            <div className="metric metric--risk" style={{ marginTop: '8px' }}>
              <div>
                <div className="metric__label">{t('field.yieldLikely')}</div>
                <div className="metric__value" style={{ color: 'var(--color-accent)' }}>
                  {fmtNum(dash.yield_forecast.likely_t_ha, 1, lang)}
                  <span className="metric__unit">{t('unit.tha')}</span>
                </div>
              </div>
              <div className="small muted">
                {t('field.yieldRange', { min: fmtNum(dash.yield_forecast.min_t_ha ?? dash.yield_forecast.pessimistic_t_ha, 1, lang), max: fmtNum(dash.yield_forecast.max_t_ha ?? dash.yield_forecast.optimistic_t_ha, 1, lang) })}
                {CONF_LABEL[dash.yield_forecast.confidence] && ` · ${t('field.confidence', { level: t(CONF_LABEL[dash.yield_forecast.confidence]) })}`}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* 7-Day Weather Forecast */}
      {dash?.forecast_daily && dash.forecast_daily.length > 0 && (
        <Card title={t('field.forecastTitle')}>
          <div className="forecast-strip">
            {dash.forecast_daily.map((d) => (
              <div key={d.date} className="forecast-day">
                <span className="forecast-day__date">{formatDay(d.date, lang)}</span>
                <span className="forecast-day__temp">
                  {d.t_max !== null ? `${Math.round(d.t_max)}°` : '—'} / {d.t_min !== null ? `${Math.round(d.t_min)}°` : '—'}
                </span>
                {d.precipitation_probability !== null && d.precipitation_probability > 0 && (
                  <span className="forecast-day__precip">
                    🌧 {d.precipitation_probability}%
                  </span>
                )}
                {d.et0_mm !== null && (
                  <span className="small muted">
                    ET₀: {fmtNum(d.et0_mm, 1, lang)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* AI Recommendations */}
      {dash?.recommendations && dash.recommendations.length > 0 && (
        <Card title={t('field.recsTitle')}>
          <div className="list">
            {dash.recommendations.map((r) => (
              <div key={r.id} className={`rec-item ${SEV[r.severity]?.cls ?? ''}`}>
                <div className="rec-item__title">
                  <span>{r.title || r.title_uz || r.problem}</span>
                  {SEV[r.severity] && <Badge tone={SEV[r.severity].tone}>{t(SEV[r.severity].label)}</Badge>}
                </div>
                {(r.cause_text ?? (lang === 'uz' ? r.cause : null)) && <div className="rec-item__body muted">{r.cause_text ?? r.cause}</div>}
                <div className="rec-item__action">👉 {r.action_text || r.action}</div>
                {r.confidence && CONF_LABEL[r.confidence] && (
                  <div className="small muted">{t('field.confidence', { level: t(CONF_LABEL[r.confidence]) })}</div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Irrigation & Agro Schedule */}
      {dash?.schedule && dash.schedule.length > 0 && (
        <Card title={t('field.scheduleTitle')}>
          <div className="list">
            {dash.schedule.map((item, idx) => (
              <div key={idx} className="schedule-item">
                <div className="schedule-item__main">
                  <span className="schedule-item__title">{item.title || item.title_uz}</span>
                  <span className="schedule-item__date">📅 {formatDay(item.date, lang)}</span>
                </div>
                {item.amount_m3_ha !== null && (
                  <span className="schedule-item__amount">
                    💧 {fmtNum(item.amount_m3_ha, 0, lang)} m³/{t('unit.ha')}
                  </span>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* IoT Devices connected */}
      {dash?.devices && dash.devices.length > 0 && (
        <Card title={t('field.devicesTitle')}>
          <div className="list">
            {dash.devices.map((dev) => (
              <div key={dev.id} className="device-row">
                <div>
                  <div className="device-row__name">📟 {dev.name}</div>
                  <div className="device-row__id">ID: {dev.device_id}</div>
                  {dev.last_seen_at && (
                    <div className="small muted">{t('field.lastSeen', { time: formatRelative(dev.last_seen_at) })}</div>
                  )}
                </div>
                <div>
                  <Badge tone={dev.status === 'online' ? 'success' : dev.status === 'offline' ? 'danger' : 'neutral'}>
                    {dev.status === 'online' ? t('field.deviceOnline') : dev.status === 'offline' ? t('field.deviceOffline') : '—'}
                  </Badge>
                  {dev.battery_v !== null && (
                    <div className="small center muted" style={{ marginTop: 2 }}>
                      🔋 {dev.battery_v.toFixed(1)}V
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <DeleteField field={f} />
    </Page>
  )
}
