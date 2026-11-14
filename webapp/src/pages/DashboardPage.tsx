/**
 * Dashboard: global satellite map centred on the farmer's region with every field coloured
 * by drying risk, and below it one card per field (GET /fields with `status`).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { getFields } from '../api/endpoints'
import type { Field } from '../api/types'
import { useAuth } from '../auth'
import { FieldCard } from '../components/field'
import { IconPlus } from '../components/icons'
import { DemoBadge, Empty, ErrorBox, Loading, Page } from '../components/ui'
import { DEFAULT_CENTER, REGION_ZOOM } from '../config'
import { useAsync } from '../hooks/useAsync'
import { useI18n } from '../i18n'
import { MapView } from '../map/MapView'
import type { MapController, MapMarker, MapPolygon } from '../map/types'
import { fieldPoint, fromGeoJsonPolygon, type LatLon } from '../utils/geo'
import { riskColor } from '../utils/status'

/** Field names are always shown on the map while there are only a few fields. */
const MAX_PERMANENT_LABELS = 10

export function DashboardPage() {
  const { farmer } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()
  const fields = useAsync(getFields, [])
  const [map, setMap] = useState<MapController | null>(null)
  const fitted = useRef(false)
  const region = farmer.farm_location
  const regionLabel = t('region.marker')

  const onReady = useCallback((m: MapController) => setMap(m), [])

  useEffect(() => {
    if (!map) return
    const list: Field[] = fields.data ?? []
    const polygons: MapPolygon[] = []
    const markers: MapMarker[] = []
    const points: LatLon[] = []
    if (region) {
      markers.push({ id: 'region', position: region, kind: 'region', label: regionLabel })
      points.push(region)
    }
    for (const f of list) {
      const color = riskColor(f.status?.drying_risk)
      const open = () => navigate(`/fields/${f.id}`)
      const ring = fromGeoJsonPolygon(f.geometry)
      if (ring.length >= 3) polygons.push({ id: `f${f.id}`, points: ring, color, label: f.name, onClick: open })
      const p = fieldPoint(f)
      if (p) {
        markers.push({ id: `m${f.id}`, position: p, kind: 'field', color, label: f.name, permanentLabel: list.length <= MAX_PERMANENT_LABELS, onClick: open })
        points.push(p)
      }
    }
    map.setPolygons(polygons)
    map.setMarkers(markers)
    // Centre once: on the region, widened to include every field.
    if (!fitted.current && fields.data) {
      fitted.current = true
      if (points.length > 1) map.fitTo(points, 15)
      else if (points.length === 1) map.setView(points[0], region ? REGION_ZOOM : 15)
    }
  }, [map, fields.data, region, regionLabel, navigate])

  const count = fields.data?.length ?? 0

  return (
    <Page
      title={t('dashboard.title')}
      subtitle={
        farmer.first_name || farmer.is_demo ? (
          <>
            {farmer.first_name ? t('dashboard.hello', { name: farmer.first_name }) : null} {farmer.is_demo && <DemoBadge />}
          </>
        ) : undefined
      }
    >
      <MapView className="map--dashboard" options={{ center: region ?? DEFAULT_CENTER, zoom: REGION_ZOOM }} onReady={onReady} />

      <div className="section-head">
        <h2 className="section-head__title">
          {t('dashboard.fields')}
          {count > 0 && <span className="section-head__count">{count}</span>}
        </h2>
        <button type="button" className="add-btn" onClick={() => navigate('/fields/new')} aria-label={t('dashboard.addField')} title={t('dashboard.addField')}>
          <IconPlus size={26} />
        </button>
      </div>

      {fields.loading && !fields.data && <Loading />}
      {fields.error && <ErrorBox error={fields.error} onRetry={fields.reload} />}
      {fields.data && fields.data.length === 0 && <Empty>{t('dashboard.empty')}</Empty>}
      {fields.data && fields.data.length > 0 && (
        <div className="list">
          {fields.data.map((f) => (
            <FieldCard key={f.id} field={f} />
          ))}
        </div>
      )}
    </Page>
  )
}
