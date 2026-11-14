/**
 * Map colours come from CSS custom properties in styles/theme.css so the whole
 * look stays in one place. Terra Draw requires hex colours, hence the fallback.
 */
import type { PolygonVariant } from './types'

export function cssVar(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

/** Returns a "#rrggbb" string (Terra Draw only accepts hex). */
export function hexVar(name: string, fallback: `#${string}`): `#${string}` {
  const v = cssVar(name, fallback)
  return /^#[0-9a-fA-F]{3,8}$/.test(v) ? (v as `#${string}`) : fallback
}

export function polygonColors(variant: PolygonVariant): { stroke: string; fill: string; fillOpacity: number; dash?: string } {
  switch (variant) {
    case 'field':
      return { stroke: hexVar('--map-field', '#22c55e'), fill: hexVar('--map-field', '#22c55e'), fillOpacity: 0.25 }
    case 'preview':
      return { stroke: hexVar('--map-draw', '#facc15'), fill: hexVar('--map-draw', '#facc15'), fillOpacity: 0.25 }
    case 'invalid':
      return { stroke: hexVar('--map-invalid', '#ef4444'), fill: hexVar('--map-invalid', '#ef4444'), fillOpacity: 0.2 }
    case 'other':
    default:
      return { stroke: hexVar('--map-other', '#e5e7eb'), fill: hexVar('--map-other', '#e5e7eb'), fillOpacity: 0.08, dash: '6 6' }
  }
}
