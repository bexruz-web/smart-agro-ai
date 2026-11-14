/**
 * Leaflet provider (default): Esri World Imagery satellite tiles + Esri place-name labels.
 */
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { LatLon } from '../utils/geo'
import { accentColor, dotSvg, outlineColor, pinSvg, regionColor } from './colors'
import type { MapController, MapFactory, MapMarker, MapPolygon } from './types'

const ESRI_IMAGERY = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const ESRI_LABELS = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
const ESRI_ATTRIBUTION =
  'Tiles &copy; <a href="https://www.esri.com/" target="_blank" rel="noopener">Esri</a> &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'

const toLL = (p: LatLon): L.LatLngExpression => [p.lat, p.lon]

function markerIcon(m: MapMarker): L.DivIcon {
  const outline = outlineColor()
  if (m.kind === 'field') {
    return L.divIcon({ className: 'map-marker', html: dotSvg(m.color ?? accentColor(), outline), iconSize: [26, 26], iconAnchor: [13, 13], tooltipAnchor: [0, -12] })
  }
  const fill = m.color ?? (m.kind === 'region' ? regionColor() : accentColor())
  return L.divIcon({ className: 'map-marker', html: pinSvg(fill, outline), iconSize: [36, 46], iconAnchor: [18, 45], tooltipAnchor: [0, -40] })
}

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

  L.tileLayer(ESRI_IMAGERY, { maxZoom: 19, maxNativeZoom: 18, attribution: ESRI_ATTRIBUTION }).addTo(map)
  L.tileLayer(ESRI_LABELS, { maxZoom: 19, maxNativeZoom: 18, opacity: 0.9 }).addTo(map)

  const polygonLayer = L.layerGroup().addTo(map)
  const markerLayer = L.layerGroup().addTo(map)
  let clickHandler: ((p: LatLon) => void) | null = null

  map.on('click', (e: L.LeafletMouseEvent) => {
    if (interactive && clickHandler) clickHandler({ lat: e.latlng.lat, lon: e.latlng.lng })
  })

  const controller: MapController = {
    provider: 'leaflet',
    setView(center, zoom) {
      map.setView(toLL(center), zoom ?? map.getZoom())
    },
    fitTo(points, maxZoom = 17) {
      if (!points.length) return
      if (points.length === 1) {
        map.setView(toLL(points[0]), maxZoom)
        return
      }
      map.fitBounds(L.latLngBounds(points.map(toLL)), { padding: [36, 36], maxZoom })
    },
    setPolygons(polygons: MapPolygon[]) {
      polygonLayer.clearLayers()
      for (const p of polygons) {
        if (p.points.length < 3) continue
        const layer = L.polygon(p.points.map(toLL), {
          color: p.color,
          weight: 3,
          fillColor: p.color,
          fillOpacity: 0.3,
          interactive: interactive && (!!p.label || !!p.onClick),
        })
        if (p.label) layer.bindTooltip(p.label, { sticky: true })
        if (p.onClick) layer.on('click', (e) => {
          L.DomEvent.stopPropagation(e)
          p.onClick?.()
        })
        polygonLayer.addLayer(layer)
      }
    },
    setMarkers(markers: MapMarker[]) {
      markerLayer.clearLayers()
      for (const m of markers) {
        const clickable = interactive && !!m.onClick
        const marker = L.marker(toLL(m.position), {
          icon: markerIcon(m),
          interactive: clickable || !!m.label,
          keyboard: clickable,
          zIndexOffset: m.kind === 'field' ? 100 : 0,
        })
        if (m.label) {
          marker.bindTooltip(m.label, {
            permanent: !!m.permanentLabel,
            direction: 'top',
            className: m.permanentLabel ? 'map-label' : undefined,
          })
        }
        if (m.onClick) marker.on('click', (e) => {
          L.DomEvent.stopPropagation(e)
          m.onClick?.()
        })
        markerLayer.addLayer(marker)
      }
    },
    onClick(handler) {
      clickHandler = handler
    },
    resize() {
      map.invalidateSize()
    },
    destroy() {
      map.off()
      map.remove()
    },
  }
  return controller
}
