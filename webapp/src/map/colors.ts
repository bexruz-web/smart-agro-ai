/** Map marker artwork shared by the providers. Colours come from CSS tokens (theme.css). */
import { tokenColor } from '../utils/status'

export const accentColor = () => tokenColor('--map-pin', '#1e6b3a')
export const regionColor = () => tokenColor('--map-region', '#1f5fa3')
export const outlineColor = () => tokenColor('--map-vertex', '#ffffff')

/** Escapes text placed into marker HTML / SVG. */
export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
}

/** Teardrop pin (36×46, tip at the bottom centre). */
export function pinSvg(fill: string, stroke: string): string {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="46" viewBox="0 0 36 46">` +
    `<path d="M18 1C8.6 1 1 8.6 1 18c0 12.4 14.6 25 16.2 26.4a1.2 1.2 0 0 0 1.6 0C20.4 43 35 30.4 35 18 35 8.6 27.4 1 18 1Z" fill="${escapeHtml(fill)}" stroke="${escapeHtml(stroke)}" stroke-width="2"/>` +
    `<circle cx="18" cy="18" r="6.5" fill="${escapeHtml(stroke)}"/></svg>`
  )
}

/** Round dot marker (field), 26×26. */
export function dotSvg(fill: string, stroke: string): string {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 26 26">` +
    `<circle cx="13" cy="13" r="10.5" fill="${escapeHtml(fill)}" stroke="${escapeHtml(stroke)}" stroke-width="3"/></svg>`
  )
}
