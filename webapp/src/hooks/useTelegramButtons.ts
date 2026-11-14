import { useEffect, useRef, useState } from 'react'
import {
  hasNativeBackButton,
  hideBackButton,
  hideMainButton,
  isInTelegram,
  showBackButton,
  showMainButton,
  updateMainButton,
} from '../telegram'

/**
 * Shows Telegram's BackButton while the component is mounted.
 * Returns true if the native button is used (the page should hide its own back button).
 */
export function useBackButton(onBack: (() => void) | null): boolean {
  const cbRef = useRef(onBack)
  cbRef.current = onBack
  const native = hasNativeBackButton()
  const enabled = !!onBack

  useEffect(() => {
    if (!enabled || !native) return
    const handler = () => cbRef.current?.()
    showBackButton(handler)
    return () => hideBackButton(handler)
  }, [enabled, native])

  return native && enabled
}

/**
 * Drives Telegram's MainButton (TG-7 "Saqlash"). Returns true when the native
 * button is shown; otherwise the page must render an on-page button.
 */
export function useMainButton(
  text: string,
  onClick: () => void,
  opts: { visible: boolean; enabled: boolean; progress?: boolean },
): boolean {
  const cbRef = useRef(onClick)
  cbRef.current = onClick
  const [native] = useState(() => isInTelegram())
  const { visible, enabled, progress } = opts

  const paramsRef = useRef({ text, enabled, progress })
  paramsRef.current = { text, enabled, progress }

  // Show/hide only when visibility changes (avoids flicker on every state change)…
  useEffect(() => {
    if (!native || !visible) return
    const handler = () => cbRef.current()
    const p = paramsRef.current
    showMainButton(p.text, handler, { enabled: p.enabled, progress: p.progress })
    return () => hideMainButton(handler)
  }, [native, visible])

  // …and update text / enabled / progress in place.
  useEffect(() => {
    if (native && visible) updateMainButton(text, { enabled, progress })
  }, [native, visible, text, enabled, progress])

  return native && visible
}
