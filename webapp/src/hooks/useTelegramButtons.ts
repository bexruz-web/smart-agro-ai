import { useEffect, useRef, useState } from "react"
import {
  hasNativeBackButton,
  hideBackButton,
  hideMainButton,
  isInTelegram,
  showBackButton,
  showMainButton,
  updateMainButton,
} from "../telegram"

export function useBackButton(onBack: (() => void) | null): boolean {
  const cbRef = useRef(onBack)
  cbRef.current = onBack
  let native = false
  try { native = hasNativeBackButton() } catch {}
  const enabled = !!onBack

  useEffect(() => {
    if (!enabled || !native) return
    const handler = () => cbRef.current?.()
    try { showBackButton(handler) } catch {}
    return () => { try { hideBackButton(handler) } catch {} }
  }, [enabled, native])

  return native && enabled
}

export function useMainButton(
  text: string,
  onClick: () => void,
  opts: { visible: boolean; enabled: boolean; progress?: boolean },
): boolean {
  const cbRef = useRef(onClick)
  cbRef.current = onClick
  const [native] = useState(() => {
    try { return isInTelegram() } catch { return false }
  })
  const { visible, enabled, progress } = opts

  const paramsRef = useRef({ text, enabled, progress })
  paramsRef.current = { text, enabled, progress }

  useEffect(() => {
    if (!native || !visible) return
    const handler = () => cbRef.current()
    const p = paramsRef.current
    try { showMainButton(p.text, handler, { enabled: p.enabled, progress: p.progress }) } catch {}
    return () => { try { hideMainButton(handler) } catch {} }
  }, [native, visible])

  useEffect(() => {
    if (native && visible) {
      try { updateMainButton(text, { enabled, progress }) } catch {}
    }
  }, [native, visible, text, enabled, progress])

  return native && visible
}
