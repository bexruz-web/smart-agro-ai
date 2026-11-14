import { useCallback, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { patchMe } from '../api/endpoints'
import { useAuth } from '../auth'
import { Page } from '../components/ui'
import { DEFAULT_CENTER, DEFAULT_ZOOM } from '../config'
import { useMainButton } from '../hooks/useTelegramButtons'
import { MapView } from '../map/MapView'
import type { MapController } from '../map/types'
import { getCurrentLocation, haptic } from '../telegram'
import { formatLatLon, type LatLon } from '../utils/geo'

/** TG-3 fallback chain end: GPS (Telegram → browser) or manual pick on the satellite map. */
export function FarmLocationPage() {
  const { farmer, setFarmer } = useAuth()
  const navigate = useNavigate()
  const mapRef = useRef<MapController | null>(null)
  const [point, setPoint] = useState<LatLon | null>(farmer.farm_location)
  const [accuracy, setAccuracy] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [gpsBusy, setGpsBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const showPoint = (p: LatLon, acc: number | null) => {
    mapRef.current?.setMarkers([{ id: 'farm', position: p, label: '🏠', accuracyM: acc }])
  }

  const onReady = useCallback(
    (map: MapController) => {
      mapRef.current = map
      if (farmer.farm_location) showPoint(farmer.farm_location, null)
      map.onClick((p) => {
        setPoint(p)
        setAccuracy(null)
        showPoint(p, null)
      })
    },
    [farmer.farm_location],
  )

  const detectGps = async () => {
    setGpsBusy(true)
    setError(null)
    try {
      const fix = await getCurrentLocation()
      const p = { lat: fix.lat, lon: fix.lon }
      setPoint(p)
      setAccuracy(fix.accuracy)
      showPoint(p, fix.accuracy)
      mapRef.current?.setView(p, 15)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setGpsBusy(false)
    }
  }

  const save = async () => {
    if (!point || busy) return
    setBusy(true)
    setError(null)
    try {
      setFarmer(await patchMe({ farm_location: point }))
      haptic('success')
      navigate(-1)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  const native = useMainButton('Saqlash', save, { visible: true, enabled: !!point && !busy, progress: busy })
  const center = farmer.farm_location ?? DEFAULT_CENTER

  return (
    <Page title="Xo'jalik joylashuvi" back={true}>
      <p className="muted">Xaritada xo'jaligingiz joyini bosing yoki GPS orqali aniqlang.</p>
      <MapView className="map--large" options={{ center, zoom: farmer.farm_location ? 14 : DEFAULT_ZOOM }} onReady={onReady} />
      <div className="btn-row">
        <button type="button" className="btn btn--secondary" onClick={detectGps} disabled={gpsBusy}>
          {gpsBusy ? 'Aniqlanmoqda…' : '📍 GPS orqali aniqlash'}
        </button>
      </div>
      <div className="muted">
        {point ? `Tanlangan: ${formatLatLon(point)}` : 'Hali tanlanmagan'}
        {accuracy !== null && ` · aniqlik ±${Math.round(accuracy)} m`}
      </div>
      {error && <div className="form-row__error">{error}</div>}
      {!native && (
        <button type="button" className="btn btn--primary btn--block btn--lg" onClick={save} disabled={!point || busy}>
          {busy ? 'Saqlanmoqda…' : 'Saqlash'}
        </button>
      )}
    </Page>
  )
}
