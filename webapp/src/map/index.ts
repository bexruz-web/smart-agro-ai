/**
 * Map provider selection. Providers are loaded lazily so the Google Maps code is
 * only downloaded when VITE_MAP_PROVIDER=google (and vice versa for Leaflet).
 */
import { config } from '../config'
import type { MapController, MapOptions } from './types'

export async function createMap(container: HTMLElement, options: MapOptions): Promise<MapController> {
  if (config.mapProvider === 'google') {
    try {
      const { createGoogleMap } = await import('./google')
      return await createGoogleMap(container, options)
    } catch (e) {
      // Bad key / blocked script → fall back to Leaflet so the farmer can still work.
      console.error('Google Maps failed to load, falling back to Leaflet', e)
      container.innerHTML = ''
    }
  }
  const { createLeafletMap } = await import('./leaflet')
  return createLeafletMap(container, options)
}

export type * from './types'
