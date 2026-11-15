/**
 * Google Maps provider (optional: VITE_MAP_PROVIDER=google + VITE_GOOGLE_MAPS_API_KEY).
 * Uses the "hybrid" (satellite + labels) map type. The API key is public in the bundle:
 * restrict it by HTTP referrer.
 */
import { importLibrary, setOptions } from '@googlemaps/js-api-loader'
import { config } from '../config'
import { getLang } from '../i18n'
import type { LatLon } from '../utils/geo'
import { accentColor, dotSvg, outlineColor, pinSvg, regionColor } from './colors'
import type { MapController, MapFactory, MapMarker } from './types'

let optionsSet = false

const toLL = (p: LatLon): google.maps.LatLngLiteral => ({ lat: p.lat, lng: p.lon })

function markerIcon(m: MapMarker): google.maps.Icon {
  const outline = outlineColor()
  if (m.kind === 'field') {
    return {
      url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(dotSvg(m.color ?? accentColor(), outline))}`,
      anchor: new google.maps.Point(13, 13),
      scaledSize: new google.maps.Size(26, 26),
    }
  }
  const fill = m.color ?? (m.kind === 'region' ? regionColor() : accentColor())
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(pinSvg(fill, outline))}`,
    anchor: new google.maps.Point(18, 45),
    scaledSize: new google.maps.Size(36, 46),
  }
}

export const createGoogleMap: MapFactory = async (container, options) => {
  if (!optionsSet) {
    setOptions({ key: config.googleMapsApiKey, v: 'weekly', language: getLang(), region: 'UZ' })
    optionsSet = true
  }
  const { Map } = await importLibrary('maps')
  await importLibrary('marker')
  const interactive = options.interactive !== false

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
  let markers: google.maps.Marker[] = []
  let clickHandler: ((p: LatLon) => void) | null = null

  map.addListener('click', (e: google.maps.MapMouseEvent) => {
    if (!interactive || !clickHandler || !e.latLng) return
    clickHandler({ lat: e.latLng.lat(), lon: e.latLng.lng() })
  })

  const controller: MapController = {
    provider: 'google',
    canDraw: false,
    setView(center, zoom) {
      map.setCenter(toLL(center))
      if (zoom !== undefined) map.setZoom(zoom)
    },
    fitTo(points, maxZoom = 17) {
      if (!points.length) return
      if (points.length === 1) {
        map.setCenter(toLL(points[0]))
        map.setZoom(maxZoom)
        return
      }
      const b = new google.maps.LatLngBounds()
      points.forEach((p) => b.extend(toLL(p)))
      map.fitBounds(b, 36)
      google.maps.event.addListenerOnce(map, 'idle', () => {
        if ((map.getZoom() ?? 0) > maxZoom) map.setZoom(maxZoom)
      })
    },
    setPolygons(list) {
      polygons.forEach((p) => p.setMap(null))
      polygons = list
        .filter((p) => p.points.length >= 3)
        .map((p) => {
          const poly = new google.maps.Polygon({
            map,
            paths: p.points.map(toLL),
            strokeColor: p.color,
            strokeWeight: 3,
            fillColor: p.color,
            fillOpacity: 0.3,
            clickable: interactive && !!p.onClick,
          })
          if (p.onClick) poly.addListener('click', () => p.onClick?.())
          return poly
        })
    },
    setMarkers(list) {
      markers.forEach((m) => m.setMap(null))
      // Classic Marker works without a Map ID (AdvancedMarkerElement requires one).
      markers = list.map((m) => {
        const marker = new google.maps.Marker({
          map,
          position: toLL(m.position),
          clickable: interactive && !!m.onClick,
          title: m.label,
          icon: markerIcon(m),
          zIndex: m.kind === 'field' ? 100 : 10,
        })
        if (m.onClick) marker.addListener('click', () => m.onClick?.())
        return marker
      })
    },
    onClick(handler) {
      clickHandler = handler
    },
    drawPolygon() {
      /* Not supported by this provider (canDraw: false): the picker offers only the pin. */
    },
    resize() {
      /* Google Maps observes its container size automatically. */
    },
    destroy() {
      polygons.forEach((p) => p.setMap(null))
      markers.forEach((m) => m.setMap(null))
      google.maps.event.clearInstanceListeners(map)
      container.innerHTML = ''
    },
  }
  return controller
}
