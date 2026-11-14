/**
 * Field page: map zoomed to the field, soil-moisture state with the 4-class legend,
 * the card metrics, "AI Agronom" / "Tahrirlash" and delete (in-page confirmation).
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { deleteField, getField, getFields } from '../api/endpoints'
import type { Field } from '../api/types'
import { FieldMetrics, MoistureLegend } from '../components/field'
import { IconChat, IconEdit, IconTrash } from '../components/icons'
import { Card, DemoBadge, ErrorBox, Loading, Page } from '../components/ui'
import { FIELD_ZOOM } from '../config'
import { useAsync } from '../hooks/useAsync'
import { useI18n } from '../i18n'
import { MapView } from '../map/MapView'
import type { MapController } from '../map/types'
import { haptic } from '../telegram'
import { fmtNum } from '../utils/format'
import { fieldPoint, fromGeoJsonPolygon } from '../utils/geo'
import { MOISTURE_LABEL, moistureKey, riskColor } from '../utils/status'

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
  const { t } = useI18n()
  const navigate = useNavigate()
  const field = useAsync(() => loadField(fieldId), [fieldId])
  const f = field.data

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

      <DeleteField field={f} />
    </Page>
  )
}
