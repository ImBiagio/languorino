// Hook di interfaccia condivisi da menu, popover e dialog.

import type { RefObject } from 'react'
import { useEffect, useRef } from 'react'

/** L'ultima versione della callback senza farla entrare nelle dipendenze dell'effetto. */
function useLatest<T>(value: T) {
  const ref = useRef(value)
  ref.current = value
  return ref
}

/** Chiude un menu aperto quando si clicca fuori dall'elemento di `ref`. */
export function useClickOutside(
  ref: RefObject<HTMLElement>,
  active: boolean,
  onOutside: () => void,
) {
  const handler = useLatest(onOutside)
  useEffect(() => {
    if (!active) return
    const onClick = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) handler.current()
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [ref, active, handler])
}

/** Esc chiude finché `active` è vero. */
export function useCloseOnEscape(active: boolean, close: () => void) {
  const handler = useLatest(close)
  useEffect(() => {
    if (!active) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') handler.current()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [active, handler])
}
