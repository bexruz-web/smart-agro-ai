import { useCallback, useMemo } from 'react'
import type { Field } from '../api/types'
import { MapView } from '../map/MapView'
import type { MapController } from '../map/types'
import { fromGeoJsonPolygon } from '../utils/geo'

/** Static satellite preview of a field polygon (dashboard). */
export function FieldMiniMap({ field }: { field: Field }) {
  const points = useMemo(() => fromGeoJsonPolygon(field.geometry), [field.geometry])
  const onReady = useCallback(
    (map: MapController) => {
      map.setPolygons([{ id: 'field', points, variant: 'field' }])
      map.fitTo(points, 18)
    },
    [points],
  )
  return <MapView className="map--small" options={{ center: field.centroid, zoom: 15, interactive: false }} onReady={onReady} />
}
