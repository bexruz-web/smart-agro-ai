import { useEffect, useRef, useState } from 'react'
import { createMap } from './index'
import type { MapController, MapOptions } from './types'

interface Props {
  options: MapOptions
  /** Called once when the map is ready; cleanup happens on unmount. */
  onReady: (map: MapController) => void
  className?: string
}

/**
 * Hosts a provider-agnostic map. Creation is async (lazy provider import), so we
 * guard against unmount (and React StrictMode double effects) before readiness.
 */
export function MapView({ options, onReady, className }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const onReadyRef = useRef(onReady)
  onReadyRef.current = onReady
  const optionsRef = useRef(options)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const host = ref.current
    if (!host) return
    // A fresh element per effect run: StrictMode's double effects never share a container.
    const el = document.createElement('div')
    el.className = 'map-view__inner'
    host.appendChild(el)
    let cancelled = false
    let ctrl: MapController | null = null
    createMap(el, optionsRef.current)
      .then((c) => {
        if (cancelled) {
          c.destroy()
          return
        }
        ctrl = c
        onReadyRef.current(c)
        // Containers inside flex layouts may get their final size after first paint.
        requestAnimationFrame(() => c.resize())
      })
      .catch((e) => {
        console.error(e)
        if (!cancelled) setError("Xaritani yuklab bo'lmadi")
      })
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => ctrl?.resize()) : null
    ro?.observe(el)
    return () => {
      cancelled = true
      ro?.disconnect()
      ctrl?.destroy()
      el.remove()
    }
  }, [])

  return (
    <div className={`map-view ${className ?? ''}`}>
      <div ref={ref} className="map-view__canvas" />
      {error && <div className="map-view__error">{error}</div>}
    </div>
  )
}
