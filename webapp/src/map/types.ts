/**
 * Map abstraction. Screens only talk to MapController, so the provider (Leaflet + Esri
 * satellite imagery by default, or Google Maps) can be swapped without touching screens.
 */
import type { LatLon } from '../utils/geo'

export interface MapPolygon {
  id: string
  points: LatLon[]
  /** Stroke / fill colour (resolved CSS colour, e.g. the drying-risk token). */
  color: string
  /** Tooltip text (e.g. the field name). */
  label?: string
  onClick?: () => void
}

/** field: risk-coloured dot · region: the farmer's region · pin: a dropped location pin. */
export type MarkerKind = 'field' | 'region' | 'pin'

export interface MapMarker {
  id: string
  position: LatLon
  kind: MarkerKind
  color?: string
  /** Tooltip text; shown permanently when `permanentLabel` is set. */
  label?: string
  permanentLabel?: boolean
  onClick?: () => void
}

export interface MapOptions {
  center: LatLon
  zoom: number
  /** false → static preview (no pan/zoom/tap). */
  interactive?: boolean
}

export interface MapController {
  readonly provider: 'leaflet' | 'google'
  setView(center: LatLon, zoom?: number): void
  /** Fit the viewport to the given points (no-op for an empty list). */
  fitTo(points: LatLon[], maxZoom?: number): void
  setPolygons(polygons: MapPolygon[]): void
  setMarkers(markers: MapMarker[]): void
  /** Map tap/click handler (null to remove). */
  onClick(handler: ((p: LatLon) => void) | null): void
  /** Call after the container size changed. */
  resize(): void
  destroy(): void
}

export type MapFactory = (container: HTMLElement, options: MapOptions) => Promise<MapController>
