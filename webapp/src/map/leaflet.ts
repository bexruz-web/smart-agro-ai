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
  const drawShapeLayer = L.layerGroup().addTo(map)
  const drawVertexLayer = L.layerGroup().addTo(map)
  let clickHandler: ((p: LatLon) => void) | null = null
  let drawHandler: ((pts: LatLon[]) => void) | null = null
  let drawPoints: LatLon[] = []
  /** Time of the last vertex drag: the click the browser may fire after it must not add a vertex. */
  let lastDragEnd = 0

  // ---- drawing helpers ----
  const DRAW_COLOR = '#22c55e'

  /** Reports a copy, so the caller can keep it (React state) while the layer goes on editing. */
  function emitDraw() {
    drawHandler?.(drawPoints.map((p) => ({ ...p })))
  }

  /** Outline (2 points) or filled polygon (3+). Redrawn on every change, also while dragging. */
  function renderDrawShape() {
    drawShapeLayer.clearLayers()
    const pts = drawPoints.map(toLL)
    if (pts.length >= 3) {
      L.polygon(pts, { color: DRAW_COLOR, weight: 2.5, fillColor: DRAW_COLOR, fillOpacity: 0.18, interactive: false }).addTo(drawShapeLayer)
    } else if (pts.length === 2) {
      L.polyline(pts, { color: DRAW_COLOR, weight: 2.5, dashArray: '6 4', interactive: false }).addTo(drawShapeLayer)
    }
  }

  /** Shape + vertex handles. Only on add/remove: re-creating a handle mid-drag would end a touch drag. */
  function renderDraw() {
    drawVertexLayer.clearLayers()
    renderDrawShape()
    if (!drawHandler) return
    drawPoints.forEach((pt, i) => {
      const m = L.circleMarker(toLL(pt), {
        radius: 9, color: '#fff', weight: 2.5, fillColor: DRAW_COLOR, fillOpacity: 1, interactive: true,
      }).addTo(drawVertexLayer)
      // A tap on a handle must not reach the map (it would add a vertex on top of it).
      m.on('click', (e) => L.DomEvent.stopPropagation(e))
      // Double tap removes the vertex.
      m.on('dblclick', (e) => {
        L.DomEvent.stopPropagation(e)
        drawPoints = drawPoints.filter((_, j) => j !== i)
        renderDraw()
        emitDraw()
      })
      // Drag moves the vertex: the handle is moved in place and only the shape is redrawn.
      const el = m.getElement()
      if (!el) return
      let moved = false
      const onMove = (ev: TouchEvent | MouseEvent) => {
        const src = 'touches' in ev ? ev.touches[0] : ev
        if (!src) return
        const box = map.getContainer().getBoundingClientRect()
        const ll = map.containerPointToLatLng([src.clientX - box.left, src.clientY - box.top])
        moved = true
        m.setLatLng(ll)
        drawPoints = drawPoints.map((p, j) => (j === i ? { lat: ll.lat, lon: ll.lng } : p))
        renderDrawShape()
        emitDraw()
      }
      const onEnd = () => {
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onEnd)
        document.removeEventListener('touchmove', onMove)
        document.removeEventListener('touchend', onEnd)
        document.removeEventListener('touchcancel', onEnd)
        if (moved) lastDragEnd = Date.now()
        moved = false
      }
      el.addEventListener('mousedown', (ev) => {
        ev.stopPropagation()
        ev.preventDefault()
        document.addEventListener('mousemove', onMove)
        document.addEventListener('mouseup', onEnd)
      })
      el.addEventListener('touchstart', (ev) => {
        ev.stopPropagation()
        document.addEventListener('touchmove', onMove, { passive: true })
        document.addEventListener('touchend', onEnd)
        document.addEventListener('touchcancel', onEnd)
      })
    })
  }

  map.on('click', (e: L.LeafletMouseEvent) => {
    if (!interactive) return
    if (drawHandler) {
      if (Date.now() - lastDragEnd < 400) return
      drawPoints = [...drawPoints, { lat: e.latlng.lat, lon: e.latlng.lng }]
      renderDraw()
      emitDraw()
      return
    }
    if (clickHandler) clickHandler({ lat: e.latlng.lat, lon: e.latlng.lng })
  })

  const controller: MapController = {
    provider: 'leaflet',
    canDraw: true,
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
    drawPolygon(opts) {
      drawHandler = opts ? opts.onChange : null
      drawPoints = opts ? opts.points.map((p) => ({ ...p })) : []
      // While drawing, a double tap edits vertices instead of zooming the map.
      if (interactive) {
        if (opts) map.doubleClickZoom.disable()
        else map.doubleClickZoom.enable()
      }
      renderDraw()
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
