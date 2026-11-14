/**
 * MapProvider abstraction (MAP-5). Screens only talk to MapController, so the
 * underlying provider (Leaflet + Esri imagery, or Google Maps) can be swapped
 * without touching business logic. Both providers draw via Terra Draw.
 */
import type { LatLon } from '../utils/geo'

export type PolygonVariant = 'field' | 'other' | 'preview' | 'invalid'

export interface MapPolygon {
  id: string
  points: LatLon[]
  variant: PolygonVariant
  /** Optional tooltip/label (e.g. other field's name). */
  label?: string
}

export interface MapMarker {
  id: string
  position: LatLon
  /** Short text inside the marker, e.g. "1".."4". */
  label: string
  /** Optional accuracy circle radius in meters (GPS corners). */
  accuracyM?: number | null
}

export type DrawState = 'idle' | 'drawing' | 'done'

export interface PolygonDrawCallbacks {
  /** Finished polygon vertices (no closing vertex), or null when nothing is drawn. */
  onChange(points: LatLon[] | null): void
  onState?(state: DrawState, canUndo: boolean): void
}

/** An active free-polygon drawing session (Terra Draw). */
export interface PolygonDrawSession {
  undo(): void
  canUndo(): boolean
  /** Finish the polygon currently being drawn (same as pressing Enter). */
  finish(): void
  /** Remove everything and start drawing again. */
  clear(): void
  /** Replace the polygon with given vertices (editable). */
  setPoints(points: LatLon[]): void
  destroy(): void
}

export interface MapOptions {
  center: LatLon
  zoom: number
  /** false → static preview (no pan/zoom/drawing), e.g. dashboard mini-map. */
  interactive?: boolean
}

export interface MapController {
  readonly provider: 'leaflet' | 'google'
  setView(center: LatLon, zoom?: number): void
  /** Fit the viewport to the given points (no-op for empty list). */
  fitTo(points: LatLon[], maxZoom?: number): void
  setPolygons(polygons: MapPolygon[]): void
  setMarkers(markers: MapMarker[]): void
  /** Map tap/click handler (null to remove). Not called while a draw session is active. */
  onClick(handler: ((p: LatLon) => void) | null): void
  startPolygonDrawing(callbacks: PolygonDrawCallbacks, initial?: LatLon[] | null): PolygonDrawSession
  /** Call after the container size changed. */
  resize(): void
  destroy(): void
}

export type MapFactory = (container: HTMLElement, options: MapOptions) => Promise<MapController>
