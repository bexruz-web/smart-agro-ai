/**
 * Leaflet provider (default): Esri World Imagery satellite tiles + optional
 * Esri labels overlay. Drawing via Terra Draw's Leaflet adapter.
 */
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { TerraDrawLeafletAdapter } from 'terra-draw-leaflet-adapter'
import type { LatLon } from '../utils/geo'
import { polygonColors, hexVar } from './colors'
import { createPolygonDrawSession } from './terraDraw'
import type { MapController, MapFactory, MapMarker, MapPolygon, PolygonDrawSession } from './types'

const ESRI_IMAGERY = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const ESRI_LABELS = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
const ESRI_ATTRIBUTION =
  'Tiles &copy; <a href="https://www.esri.com/" target="_blank" rel="noopener">Esri</a> &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'

const toLL = (p: LatLon): L.LatLngExpression => [p.lat, p.lon]

export const createLeafletMap: MapFactory = async (container, options) => {
  const interactive = options.interactive !== false
  const map = L.map(container, {
    center: toLL(options.center),
    zoom: options.zoom,
    zoomControl: interactive,
    attributionControl: true,
    dragging: interactive,
    touchZoom: interactive,
    scrollWheelZoom: interactive,
    doubleClickZoom: interactive,
    boxZoom: false,
    keyboard: interactive,
  })
  map.attributionControl.setPrefix('<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>')

  L.tileLayer(ESRI_IMAGERY, { maxZoom: 20, maxNativeZoom: 18, attribution: ESRI_ATTRIBUTION }).addTo(map)
  const labels = L.tileLayer(ESRI_LABELS, { maxZoom: 20, maxNativeZoom: 18, opacity: 0.9 })
  labels.addTo(map)
  if (interactive) L.control.layers(undefined, { 'Nomlar va chegaralar': labels }, { position: 'topright' }).addTo(map)

  const polygonLayer = L.layerGroup().addTo(map)
  const markerLayer = L.layerGroup().addTo(map)
  let clickHandler: ((p: LatLon) => void) | null = null
  let session: PolygonDrawSession | null = null

  map.on('click', (e: L.LeafletMouseEvent) => {
    if (session || !clickHandler) return
    clickHandler({ lat: e.latlng.lat, lon: e.latlng.lng })
  })

  const controller: MapController = {
    provider: 'leaflet',
    setView(center, zoom) {
      map.setView(toLL(center), zoom ?? map.getZoom())
    },
    fitTo(points, maxZoom = 17) {
      if (!points.length) return
      if (points.length === 1) {
        map.setView(toLL(points[0]), Math.min(maxZoom, 16))
        return
      }
      map.fitBounds(L.latLngBounds(points.map(toLL)), { padding: [24, 24], maxZoom })
    },
    setPolygons(polygons: MapPolygon[]) {
      polygonLayer.clearLayers()
      for (const p of polygons) {
        if (p.points.length < 2) continue
        const c = polygonColors(p.variant)
        const layer = L.polygon(p.points.map(toLL), {
          color: c.stroke,
          weight: p.variant === 'other' ? 2 : 3,
          fillColor: c.fill,
          fillOpacity: c.fillOpacity,
          dashArray: c.dash,
          interactive: !!p.label,
        })
        if (p.label) layer.bindTooltip(p.label, { sticky: true })
        polygonLayer.addLayer(layer)
      }
    },
    setMarkers(markers: MapMarker[]) {
      markerLayer.clearLayers()
      for (const m of markers) {
        if (m.accuracyM && m.accuracyM > 0) {
          const accent = hexVar('--map-draw', '#facc15')
          markerLayer.addLayer(
            L.circle(toLL(m.position), { radius: m.accuracyM, color: accent, weight: 1, fillOpacity: 0.1, interactive: false }),
          )
        }
        const icon = L.divIcon({ className: 'map-pin', html: `<span>${m.label}</span>`, iconSize: [28, 28], iconAnchor: [14, 14] })
        markerLayer.addLayer(L.marker(toLL(m.position), { icon, interactive: false, keyboard: false }))
      }
    },
    onClick(handler) {
      clickHandler = handler
    },
    startPolygonDrawing(callbacks, initial) {
      session?.destroy()
      const adapter = new TerraDrawLeafletAdapter({ lib: L, map, coordinatePrecision: 9 })
      const s = createPolygonDrawSession({ adapter, keyTarget: () => map.getContainer() }, callbacks, initial)
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
      map.invalidateSize()
    },
    destroy() {
      session?.destroy()
      map.off()
      map.remove()
    },
  }
  return controller
}
