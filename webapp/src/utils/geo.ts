/** Small geometry helpers for showing fields on the map. */
import type { GeoJsonPolygon, LatLonDto } from '../api/types'

export type LatLon = LatLonDto

/** Two points closer than this (degrees, ≈1 cm) are treated as the same vertex. */
const EPS = 1e-7

export function samePoint(a: LatLon, b: LatLon): boolean {
  return Math.abs(a.lat - b.lat) < EPS && Math.abs(a.lon - b.lon) < EPS
}

export function isValidLatLon(p: LatLon | null | undefined): p is LatLon {
  return (
    !!p &&
    Number.isFinite(p.lat) &&
    Number.isFinite(p.lon) &&
    p.lat >= -90 &&
    p.lat <= 90 &&
    p.lon >= -180 &&
    p.lon <= 180
  )
}

/** Exterior ring of a GeoJSON polygon as LatLon[] without the closing vertex. */
export function fromGeoJsonPolygon(geom: GeoJsonPolygon | null | undefined): LatLon[] {
  const ring = geom?.coordinates?.[0] ?? []
  const pts = ring.filter((c) => Array.isArray(c) && c.length >= 2).map(([lon, lat]) => ({ lat, lon }))
  if (pts.length > 1 && samePoint(pts[0], pts[pts.length - 1])) pts.pop()
  return pts
}

/** Where a field is shown: its pinned location, else the centroid, else the polygon's mean point. */
export function fieldPoint(f: { location?: LatLon | null; centroid?: LatLon | null; geometry?: GeoJsonPolygon | null }): LatLon | null {
  if (isValidLatLon(f.location)) return f.location
  if (isValidLatLon(f.centroid)) return f.centroid
  const pts = fromGeoJsonPolygon(f.geometry)
  if (!pts.length) return null
  return { lat: pts.reduce((s, p) => s + p.lat, 0) / pts.length, lon: pts.reduce((s, p) => s + p.lon, 0) / pts.length }
}

export function formatLatLon(p: LatLon, digits = 5): string {
  return `${p.lat.toFixed(digits)}, ${p.lon.toFixed(digits)}`
}
