// Il dialog di conferma dell'app al posto di window.confirm: stessa superficie
// M3 delle modali, bottoni dell'app, traducibile. `useConfirm()` restituisce una
// funzione che apre il dialog e risolve a true / false, cosi' chi lo usa scrive
// `if (!(await confirm({...}))) return` come prima con window.confirm.

import clsx from 'clsx'
import type { ReactNode } from 'react'
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

import { useCloseOnEscape } from '../lib/hooks'
import { gettext } from '../lib/i18n'
import { Icon } from './ui'

export interface ConfirmOptions {
  title: string
  message?: ReactNode
  /** Testo del bottone che conferma, es. "Elimina". */
  confirmLabel?: string
  cancelLabel?: string
  icon?: string
  /** Azione che toglie qualcosa: bottone e icona in rosso. */
  destructive?: boolean
}

type Confirm = (options: ConfirmOptions) => Promise<boolean>

const ConfirmContext = createContext<Confirm | null>(null)

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null)
  const resolver = useRef<((value: boolean) => void) | null>(null)

  const confirm = useCallback<Confirm>((next) => {
    // Un dialog gia' aperto vale come annullato: non resta una promise appesa.
    resolver.current?.(false)
    setOptions(next)
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve
    })
  }, [])

  const close = useCallback((value: boolean) => {
    resolver.current?.(value)
    resolver.current = null
    setOptions(null)
  }, [])

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {options && <ConfirmDialog options={options} onClose={close} />}
    </ConfirmContext.Provider>
  )
}

export function useConfirm(): Confirm {
  const confirm = useContext(ConfirmContext)
  if (!confirm) throw new Error('useConfirm va usato dentro ConfirmProvider')
  return confirm
}

/** Basic dialog M3: icona, titolo, testo, azioni a destra. Centrato anche su mobile. */
function ConfirmDialog({
  options,
  onClose,
}: {
  options: ConfirmOptions
  onClose: (value: boolean) => void
}) {
  const confirmButton = useRef<HTMLButtonElement>(null)
  useCloseOnEscape(true, () => onClose(false))
  useEffect(() => {
    confirmButton.current?.focus()
  }, [])

  const destructive = Boolean(options.destructive)
  const icon = options.icon ?? (destructive ? 'delete' : 'help')

  return (
    // z-70: sopra le modali (z-60), da cui a volte parte la conferma.
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center p-6"
      style={{ background: 'var(--scrim)' }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose(false)
      }}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby={options.message ? 'confirm-message' : undefined}
        className="w-full min-w-[280px] max-w-[400px] rounded-panel bg-surface-container-high p-6 shadow-sheet"
      >
        <div className="flex flex-col items-center text-center">
          <Icon name={icon} size={24} className={destructive ? 'text-error' : 'text-secondary'} />
          <h2 id="confirm-title" className="mt-4 text-[24px] font-medium leading-8">
            {options.title}
          </h2>
        </div>
        {options.message && (
          <div id="confirm-message" className="mt-4 text-body-medium text-on-surface-variant">
            {options.message}
          </div>
        )}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <button type="button" className="btn-text" onClick={() => onClose(false)}>
            {options.cancelLabel ?? gettext('Annulla')}
          </button>
          <button
            ref={confirmButton}
            type="button"
            onClick={() => onClose(true)}
            className={clsx(destructive ? 'btn bg-error text-on-primary' : 'btn-filled')}
          >
            {options.confirmLabel ?? gettext('Conferma')}
          </button>
        </div>
      </div>
    </div>
  )
}
