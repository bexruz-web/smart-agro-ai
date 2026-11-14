/**
 * Google Maps provider (optional: VITE_MAP_PROVIDER=google + VITE_GOOGLE_MAPS_API_KEY).
 * Uses the "hybrid" (satellite + labels) map type. The removed Google Drawing
 * Library is replaced by Terra Draw's Google Maps adapter (MAP-5).
 * The API key is public in the bundle: restrict it by HTTP referrer (MAP-6).
 */
import { importLibrary, setOptions } from '@googlemaps/js-api-loader'
import { TerraDrawGoogleMapsAdapter } from 'terra-draw-google-maps-adapter'
import { config } from '../config'
import type { LatLon } from '../utils/geo'
import { hexVar, polygonColors } from './colors'
import { createPolygonDrawSession } from './terraDraw'
import type { MapController, MapFactory, PolygonDrawSession } from './types'

let optionsSet = false

const toLL = (p: LatLon): google.maps.LatLngLiteral => ({ lat: p.lat, lng: p.lon })

export const createGoogleMap: MapFactory = async (container, options) => {
  if (!optionsSet) {
    setOptions({ key: config.googleMapsApiKey, v: 'weekly', language: 'uz', region: 'UZ' })
    optionsSet = true
  }
  const { Map } = await importLibrary('maps')
  await importLibrary('marker')
  const interactive = options.interactive !== false

  // Terra Draw's Google adapter needs the map element to have an id.
  if (!container.id) container.id = `gmap-${Math.random().toString(36).slice(2)}`

  const map = new Map(container, {
    center: toLL(options.center),
    zoom: options.zoom,
    mapTypeId: 'hybrid',
    tilt: 0,
    clickableIcons: false,
    disableDefaultUI: !interactive,
    zoomControl: interactive,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false,
    gestureHandling: interactive ? 'greedy' : 'none',
    keyboardShortcuts: interactive,
    ...(config.googleMapsMapId ? { mapId: config.googleMapsMapId } : {}),
  })

  let polygons: google.maps.Polygon[] = []
  let overlays: (google.maps.Marker | google.maps.Circle)[] = []
  let clickHandler: ((p: LatLon) => void) | null = null
  let session: PolygonDrawSession | null = null

  map.addListener('click', (e: google.maps.MapMouseEvent) => {
    if (session || !clickHandler || !e.latLng) return
    clickHandler({ lat: e.latLng.lat(), lon: e.latLng.lng() })
  })

  const controller: MapController = {
    provider: 'google',
    setView(center, zoom) {
      map.setCenter(toLL(center))
      if (zoom !== undefined) map.setZoom(zoom)
    },
    fitTo(points, maxZoom = 17) {
      if (!points.length) return
      if (points.length === 1) {
        map.setCenter(toLL(points[0]))
        map.setZoom(Math.min(maxZoom, 16))
        return
      }
      const b = new google.maps.LatLngBounds()
      points.forEach((p) => b.extend(toLL(p)))
      map.fitBounds(b, 24)
      google.maps.event.addListenerOnce(map, 'idle', () => {
        if ((map.getZoom() ?? 0) > maxZoom) map.setZoom(maxZoom)
      })
    },
    setPolygons(list) {
      polygons.forEach((p) => p.setMap(null))
      polygons = list
        .filter((p) => p.points.length >= 2)
        .map((p) => {
          const c = polygonColors(p.variant)
          return new google.maps.Polygon({
            map,
            paths: p.points.map(toLL),
            strokeColor: c.stroke,
            strokeWeight: p.variant === 'other' ? 2 : 3,
            fillColor: c.fill,
            fillOpacity: c.fillOpacity,
            clickable: false,
          })
        })
    },
    setMarkers(markers) {
      overlays.forEach((o) => o.setMap(null))
      overlays = []
      const accent = hexVar('--map-draw', '#facc15')
      const pinText = hexVar('--map-pin-text', '#111111')
      const vertex = hexVar('--map-vertex', '#ffffff')
      for (const m of markers) {
        if (m.accuracyM && m.accuracyM > 0) {
          overlays.push(
            new google.maps.Circle({ map, center: toLL(m.position), radius: m.accuracyM, strokeColor: accent, strokeWeight: 1, fillOpacity: 0.1, clickable: false }),
          )
        }
        // Classic Marker works without a Map ID (AdvancedMarkerElement requires one).
        overlays.push(
          new google.maps.Marker({
            map,
            position: toLL(m.position),
            clickable: false,
            label: { text: m.label, color: pinText, fontWeight: '700' },
            icon: { path: google.maps.SymbolPath.CIRCLE, scale: 12, fillColor: accent, fillOpacity: 1, strokeColor: vertex, strokeWeight: 2 },
          }),
        )
      }
    },
    onClick(handler) {
      clickHandler = handler
    },
    startPolygonDrawing(callbacks, initial) {
      session?.destroy()
      const adapter = new TerraDrawGoogleMapsAdapter({ lib: google.maps, map, coordinatePrecision: 9 })
      const s = createPolygonDrawSession(
        {
          adapter,
          keyTarget: () => container,
          // The adapter needs the map projection before starting.
          whenReady: (start) => {
            if (map.getProjection()) start()
            else google.maps.event.addListenerOnce(map, 'projection_changed', start)
          },
        },
        callbacks,
        initial,
      )
      const wrapped: PolygonDrawSession = {
        ...s,
        destroy() {
          s.destroy()
          if (session === wrapped) session = null
        },
      }
      session = wrapped
      return wrapped
    },
    resize() {
      /* Google Maps observes its container size automatically. */
    },
    destroy() {
      session?.destroy()
      polygons.forEach((p) => p.setMap(null))
      overlays.forEach((o) => o.setMap(null))
      google.maps.event.clearInstanceListeners(map)
      container.innerHTML = ''
    },
  }
  return controller
}
