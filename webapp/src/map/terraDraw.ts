/**
 * Provider-agnostic free-polygon drawing session built on Terra Draw (MAP-1b).
 * Only the adapter differs between Leaflet and Google Maps.
 *
 * Flow: polygon mode (tap to add vertices, tap first vertex / "Yakunlash" to close)
 * → after finishing we switch to select mode so vertices can be dragged,
 * midpoints dragged to insert vertices, and vertices deleted. Undo uses Terra Draw's
 * mode-level (while drawing: last vertex) and session-level (after finishing: edits) stacks.
 */
import {
  TerraDraw,
  TerraDrawModeUndoRedo,
  TerraDrawPolygonMode,
  TerraDrawSelectMode,
  TerraDrawSessionUndoRedo,
  type GeoJSONStoreFeatures,
} from 'terra-draw'
import type { LatLon } from '../utils/geo'
import { fromGeoJsonPolygon } from '../utils/geo'
import { hexVar } from './colors'
import type { DrawState, PolygonDrawCallbacks, PolygonDrawSession } from './types'

type TerraDrawAdapter = ConstructorParameters<typeof TerraDraw>[0]['adapter']

const POLYGON = 'polygon'
const SELECT = 'select'

/** Terra Draw rejects coordinates with more decimals than its precision (default 9). */
const round7 = (n: number) => Math.round(n * 1e7) / 1e7

export interface TerraDrawHost {
  adapter: TerraDrawAdapter
  /** Element that receives keyboard events (adapter.getMapEventElement()). */
  keyTarget: () => HTMLElement | null
  /** Some adapters (Google) can only start once the map projection is ready. */
  whenReady?: (start: () => void) => void
}

export function createPolygonDrawSession(
  host: TerraDrawHost,
  callbacks: PolygonDrawCallbacks,
  initial?: LatLon[] | null,
): PolygonDrawSession {
  const draw = hexVar('--map-draw', '#facc15')
  const vertex = hexVar('--map-vertex', '#ffffff')

  const td = new TerraDraw({
    adapter: host.adapter,
    modes: [
      new TerraDrawPolygonMode({
        editable: true,
        styles: {
          fillColor: draw,
          fillOpacity: 0.25,
          outlineColor: draw,
          outlineWidth: 3,
          closingPointColor: vertex,
          closingPointOutlineColor: draw,
          closingPointWidth: 9,
          closingPointOutlineWidth: 3,
          editedPointColor: vertex,
          editedPointOutlineColor: draw,
          coordinatePointColor: vertex,
          coordinatePointOutlineColor: draw,
        },
      }),
      new TerraDrawSelectMode({
        allowManualDeselection: false,
        flags: {
          [POLYGON]: {
            feature: {
              draggable: false,
              coordinates: { draggable: true, midpoints: true, deletable: true },
            },
          },
        },
        styles: {
          selectedPolygonColor: draw,
          selectedPolygonFillOpacity: 0.25,
          selectedPolygonOutlineColor: draw,
          selectedPolygonOutlineWidth: 3,
          selectionPointColor: vertex,
          selectionPointOutlineColor: draw,
          selectionPointWidth: 8,
          selectionPointOutlineWidth: 3,
          midPointColor: draw,
          midPointOutlineColor: vertex,
          midPointWidth: 5,
        },
      }),
    ],
    undoRedo: {
      modeLevel: new TerraDrawModeUndoRedo(),
      sessionLevel: new TerraDrawSessionUndoRedo(),
    },
  })

  let running = false // td.start() called
  let started = false // adapter ready, modes set up
  let destroyed = false

  const finishedPolygon = (): GeoJSONStoreFeatures | undefined =>
    td
      .getSnapshot()
      .find((f) => f.geometry.type === 'Polygon' && f.properties.mode === POLYGON && !f.properties.currentlyDrawing)

  const emit = () => {
    if (!started || destroyed) return
    const feature = finishedPolygon()
    const points = feature ? fromGeoJsonPolygon(feature.geometry as never) : null
    callbacks.onChange(points && points.length >= 3 ? points : null)
    let state: DrawState = 'idle'
    if (td.getModeState() === 'drawing') state = 'drawing'
    else if (feature) state = 'done'
    callbacks.onState?.(state, td.canUndo())
    // Undo removed the finished polygon while in select mode → allow drawing again.
    if (!feature && td.getMode() === SELECT) queueMicrotask(() => !destroyed && td.setMode(POLYGON))
  }

  const loadPoints = (pts: LatLon[]) => {
    td.clear()
    if (pts.length < 3) {
      td.setMode(POLYGON)
      return
    }
    const ring = pts.map((p) => [round7(p.lon), round7(p.lat)])
    ring.push([...ring[0]])
    const id = td.getFeatureId()
    const result = td.addFeatures([
      { id, type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: { mode: POLYGON } },
    ])
    if (result[0]?.valid) {
      td.setMode(SELECT)
      td.selectFeature(id)
    } else {
      console.warn('Terra Draw rejected polygon', result[0]?.reason)
      td.setMode(POLYGON)
    }
    td.clearUndoRedoHistory()
  }

  // Called once the adapter is ready (Leaflet: synchronously inside start(); Google: after its
  // OverlayView is added and has a projection). Deferred so td.start() has fully completed.
  const onReady = () => {
    if (destroyed || started) return
    started = true
    td.on('change', emit)
    td.on('history', emit)
    td.on('finish', (id, ctx) => {
      if (ctx.action === 'draw') {
        // Keep exactly one field polygon: switch to vertex editing.
        td.setMode(SELECT)
        td.selectFeature(id)
      }
      emit()
    })
    if (initial && initial.length >= 3) loadPoints(initial)
    else td.setMode(POLYGON)
    emit()
  }

  const start = () => {
    if (destroyed) return
    td.on('ready', () => queueMicrotask(onReady))
    td.start()
    running = true
  }

  if (host.whenReady) host.whenReady(start)
  else start()

  return {
    undo() {
      if (started && td.canUndo()) td.undo()
      emit()
    },
    canUndo: () => started && td.canUndo(),
    finish() {
      // Terra Draw's polygon mode closes the ring on its "finish" key (Enter).
      const el = host.keyTarget()
      el?.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }))
    },
    clear() {
      if (!started) return
      td.clear()
      td.clearUndoRedoHistory()
      td.setMode(POLYGON)
      emit()
    },
    setPoints(points: LatLon[]) {
      if (!started) return
      loadPoints(points)
      emit()
    },
    destroy() {
      destroyed = true
      if (running) {
        try {
          td.stop()
        } catch {
          /* map may already be gone */
        }
      }
    },
  }
}
