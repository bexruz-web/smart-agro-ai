import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react'

export interface AsyncState<T> {
  data: T | undefined
  error: Error | null
  loading: boolean
  reload: () => void
  setData: (updater: T | ((prev: T | undefined) => T)) => void
}

/** Runs an async loader on mount / when deps change; ignores stale responses. */
export function useAsync<T>(loader: () => Promise<T>, deps: DependencyList): AsyncState<T> {
  const [data, setDataState] = useState<T | undefined>(undefined)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)
  const [nonce, setNonce] = useState(0)
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    loaderRef
      .current()
      .then((d) => {
        if (alive) setDataState(d)
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e : new Error(String(e)))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  const setData = useCallback((updater: T | ((prev: T | undefined) => T)) => {
    setDataState((prev) => (typeof updater === 'function' ? (updater as (p: T | undefined) => T)(prev) : updater))
  }, [])

  return { data, error, loading, reload, setData }
}
