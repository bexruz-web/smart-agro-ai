/**
 * PolygonPicker — field location on the map: drop a single pin, or draw the field boundary.
 *
 *   "pin"  — a tap on the map places the pin (onPin).
 *   "draw" — every tap adds a vertex; vertices can be dragged, a double tap removes one.
 *            The parent only receives complete polygons (3+ vertices, else null) via onPolygon.
 *
 * The draw layer owns the vertices while drawing; this component mirrors them locally (for the
 * progress text and the Clear button) and re-initialises the layer only when the map becomes
 * ready, the mode changes or Clear is pressed. Only the active mode's value is kept in the form;
 * the other one is remembered here, so switching back restores it.
 * `polygon` is read once (initial value); `pin` is controlled.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { FIELD_ZOOM } from '../config'
import { useI18n } from '../i18n'
import { MapView } from '../map/MapView'
import type { MapController, MapOptions } from '../map/types'
import { haptic } from '../telegram'
import { fmtNum } from '../utils/format'
import { POLYGON_MIN_POINTS, formatLatLon, polygonAreaHa, polygonCentroid, type LatLon } from '../utils/geo'

type Mode = 'pin' | 'draw'

interface PolygonPickerProps {
  pin: LatLon | null
  polygon: LatLon[] | null
  onPin: (p: LatLon | null) => void
  onPolygon: (pts: LatLon[] | null) => void
  /** Map view when there is no pin / polygon yet (the farmer's region). */
  fallbackCenter: { center: LatLon; zoom: number }
}

export function PolygonPicker({ pin, polygon, onPin, onPolygon, fallbackCenter }: PolygonPickerProps) {
  const { t, lang } = useI18n()
  const [map, setMap] = useState<MapController | null>(null)
  const [mode, setMode] = useState<Mode>(() => ((polygon?.length ?? 0) >= POLYGON_MIN_POINTS ? 'draw' : 'pin'))
  /** Every vertex placed so far (also 1–2, which the parent does not get). */
  const [vertices, setVertices] = useState<LatLon[]>(() => polygon ?? [])
  /** Bumped by Clear to start the draw layer again. */
  const [drawRun, setDrawRun] = useState(0)
  /** Value of the inactive mode, restored when switching back. */
  const savedPin = useRef<LatLon | null>(null)

  const onPinRef = useRef(onPin)
  onPinRef.current = onPin
  const onPolygonRef = useRef(onPolygon)
  onPolygonRef.current = onPolygon
  const verticesRef = useRef(vertices)
  verticesRef.current = vertices

  // MapView reads its options once: open on the existing field (edit) or on the region.
  const [initialView] = useState<MapOptions>(() => {
    const start = pin ?? (polygon?.length ? polygonCentroid(polygon) : null)
    return start ? { center: start, zoom: FIELD_ZOOM } : fallbackCenter
  })

  const onReady = useCallback((m: MapController) => setMap(m), [])

  // Pin mode: a tap places the pin.
  useEffect(() => {
    if (!map || mode !== 'pin') return
    map.onClick((p) => {
      onPinRef.current(p)
      haptic('light')
    })
    return () => map.onClick(null)
  }, [map, mode])

  useEffect(() => {
    map?.setMarkers(mode === 'pin' && pin ? [{ id: 'pin', position: pin, kind: 'pin' }] : [])
  }, [map, mode, pin])

  // Draw mode: (re)start the draw layer with the current vertices — not on every change.
  useEffect(() => {
    if (!map || mode !== 'draw') return
    map.drawPolygon({
      points: verticesRef.current,
      onChange: (pts) => {
        setVertices(pts)
        onPolygonRef.current(pts.length >= POLYGON_MIN_POINTS ? pts : null)
      },
    })
    return () => map.drawPolygon(null)
  }, [map, mode, drawRun])

  const switchMode = (next: Mode) => {
    if (next === mode) return
    if (next === 'draw') {
      savedPin.current = pin
      onPinRef.current(null)
      onPolygonRef.current(vertices.length >= POLYGON_MIN_POINTS ? vertices : null)
    } else {
      onPolygonRef.current(null)
      if (savedPin.current) onPinRef.current(savedPin.current)
    }
    setMode(next)
    haptic('light')
  }

  const clearPolygon = () => {
    setVertices([])
    verticesRef.current = []
    onPolygonRef.current(null)
    setDrawRun((n) => n + 1)
    haptic('light')
  }

  const canDraw = map?.canDraw ?? true
  const count = vertices.length
  const complete = count >= POLYGON_MIN_POINTS
  const canClear = count > 0
  let drawText = t('form.polygonHint')
  if (complete) drawText = t('form.polygonPoints', { n: count })
  else if (canClear) drawText = `${t('form.polygonPoints', { n: count })} — ${t('form.polygonMore', { n: POLYGON_MIN_POINTS - count })}`
  const areaHa = complete ? polygonAreaHa(vertices) : 0
  const areaText = areaHa > 0 ? ` · ≈${fmtNum(areaHa, 2, lang)} ${t('unit.ha')}` : ''

  return (
    <div className="polygon-picker">
      {canDraw && (
        <div className="polygon-picker__tabs" role="tablist" aria-label={t('form.methodTab')}>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'pin'}
            className={`polygon-picker__tab ${mode === 'pin' ? 'is-active' : ''}`}
            onClick={() => switchMode('pin')}
          >
            📍 {t('form.polygonPin')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'draw'}
            className={`polygon-picker__tab ${mode === 'draw' ? 'is-active' : ''}`}
            onClick={() => switchMode('draw')}
          >
            ✏️ {t('form.polygonDraw')}
          </button>
        </div>
      )}

      <MapView className="map--picker" options={initialView} onReady={onReady} />

      {mode === 'pin' && (
        <div className="polygon-picker__status">
          {pin ? (
            <span className="polygon-picker__ok">📍 {t('form.locationSet', { coords: formatLatLon(pin, 5) })}</span>
          ) : (
            <span className="polygon-picker__hint">{t('form.locationHint')}</span>
          )}
        </div>
      )}

      {mode === 'draw' && (
        <div className="polygon-picker__status">
          {complete ? (
            <span className="polygon-picker__ok">
              ✅ {drawText}
              {areaText && <span className="polygon-picker__area">{areaText}</span>}
            </span>
          ) : (
            <span className="polygon-picker__hint">{drawText}</span>
          )}
          {canClear && (
            <button type="button" className="polygon-picker__clear" onClick={clearPolygon}>
              🗑 {t('form.polygonClear')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
