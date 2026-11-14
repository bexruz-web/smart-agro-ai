/**
 * First entry: "Hududingizni tanlang" — pick the region on the map or send the current
 * location (Telegram LocationManager → navigator.geolocation) → PATCH /me farm_location.
 */
import { useCallback, useRef, useState } from 'react'
import { patchMe } from '../api/endpoints'
import { useAuth } from '../auth'
import { IconPin } from '../components/icons'
import { ErrorBox, Page } from '../components/ui'
import { DEFAULT_CENTER, DEFAULT_ZOOM, REGION_ZOOM } from '../config'
import { useMainButton } from '../hooks/useTelegramButtons'
import { useI18n } from '../i18n'
import { MapView } from '../map/MapView'
import type { MapController } from '../map/types'
import { LocationError, getCurrentLocation, haptic } from '../telegram'
import { formatLatLon, type LatLon } from '../utils/geo'

export function RegionPage() {
  const { setFarmer } = useAuth()
  const { t } = useI18n()
  const mapRef = useRef<MapController | null>(null)
  const [point, setPoint] = useState<LatLon | null>(null)
  const [saving, setSaving] = useState(false)
  const [locating, setLocating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const labelRef = useRef('')
  labelRef.current = t('region.marker')

  const showPoint = (p: LatLon) => {
    mapRef.current?.setMarkers([{ id: 'region', position: p, kind: 'region', label: labelRef.current }])
  }

  const onReady = useCallback((map: MapController) => {
    mapRef.current = map
    map.onClick((p) => {
      setError(null)
      setPoint(p)
      showPoint(p)
    })
  }, [])

  const save = async (p: LatLon | null = point) => {
    if (!p || saving) return
    setSaving(true)
    setError(null)
    try {
      const farmer = await patchMe({ farm_location: { lat: p.lat, lon: p.lon } })
      haptic('success')
      // farm_location is now set → the app shows the Dashboard centred on this region.
      setFarmer(farmer)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
      setSaving(false)
    }
  }

  const sendLocation = async () => {
    setLocating(true)
    setError(null)
    try {
      const fix = await getCurrentLocation()
      const p = { lat: fix.lat, lon: fix.lon }
      setPoint(p)
      showPoint(p)
      mapRef.current?.setView(p, REGION_ZOOM)
      await save(p)
    } catch (e) {
      setError(e instanceof LocationError ? t(`location.${e.code}`) : e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setLocating(false)
    }
  }

  useMainButton(t('region.confirm'), () => save(), { visible: !!point, enabled: !!point && !saving, progress: saving })

  return (
    <Page title={t('region.title')}>
      <p className="lead">{t('region.text')}</p>
      <button type="button" className="btn btn--primary btn--block btn--lg" onClick={sendLocation} disabled={locating || saving}>
        <IconPin size={20} /> {locating ? t('region.locating') : t('region.sendLocation')}
      </button>
      <MapView className="map--region" options={{ center: DEFAULT_CENTER, zoom: DEFAULT_ZOOM }} onReady={onReady} />
      <div className="muted center">{point ? t('region.selected', { coords: formatLatLon(point, 4) }) : t('region.notSelected')}</div>
      {error && <ErrorBox error={error} />}
      <button type="button" className="btn btn--secondary btn--block btn--lg" onClick={() => save()} disabled={!point || saving}>
        {saving ? t('common.saving') : t('region.confirm')}
      </button>
    </Page>
  )
}
