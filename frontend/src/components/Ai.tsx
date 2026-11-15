import clsx from 'clsx'

import { useAiQuote, useAiWallet } from '../api/hooks'
import { gettext, interpolate } from '../lib/i18n'
import { Icon } from './ui'

/**
 * Le pannocchie 🌽 di oggi: la quota della chiave di casa per le funzioni AI
 * piccole (ADR 0021). Sta nelle barre di navigazione, in fondo al rail su
 * desktop e come ultima voce della barra in basso su mobile (in alto gli
 * angoli sono occupati dai bottoni delle pagine, es. il dettaglio ricetta),
 * con la stessa forma delle voci: pannocchia sopra, numero sotto. Porta alla
 * pagina AI dell'account su cornhub. Se cornhub non risponde non si mostra.
 */
export function CornCounter() {
  const { data } = useAiWallet()
  if (data?.pannocchie_left === undefined) return null
  const left = data.pannocchie_left
  const day = data.pannocchie_day ?? 0
  const low = day > 0 && left < day / 5
  const title = interpolate(
    gettext('Pannocchie rimaste oggi: %s su %s. Quota gratuita per le funzioni AI piccole.'),
    [left, day],
  )
  return (
    <a
      href={data.account_url}
      title={title}
      aria-label={title}
      className="flex shrink-0 flex-col items-center gap-1 no-underline"
    >
      <span
        className={clsx(
          'state flex items-center justify-center text-[18px] transition-colors duration-200 ease-m3',
          low
            ? 'bg-error-container text-on-error-container'
            : 'bg-tertiary-container text-on-tertiary-container',
        )}
        style={{ width: 48, height: 32, borderRadius: 16 }}
      >
        {/* Le pannocchie sono l'unita' della quota: niente traduzione. */}
        <span aria-hidden="true">🌽</span>
      </span>
      <span
        className={clsx(
          'text-center text-label-small tabular-nums',
          low ? 'text-error' : 'text-on-surface-variant',
        )}
      >
        {left}
      </span>
    </a>
  )
}

/**
 * Stato di una funzione AI per il suo bottone. Le funzioni grandi usano la
 * chiave dell'utente: il bottone mostra la chiave (``AiKeyIcon``) e resta
 * spento finche' l'utente non ne ha una adatta (``allowed`` false, con il
 * motivo in ``message``, che ``AiCost`` mostra accanto con il link).
 * ``count`` e ``fast`` come in ``AiCost``, cosi' la stima e' la stessa;
 * ``enabled`` false finche' il bottone non si vede (niente stima inutile).
 */
export function useAiGate(feature: string, { count = 1, fast = false, enabled = true } = {}) {
  const n = Math.max(1, Math.round(count))
  const features = n > 1 ? [`${feature}:${n}`] : [feature]
  const { data, isLoading } = useAiQuote(features, fast, enabled)
  const item = data?.items[0]
  return {
    loading: isLoading,
    large: item?.tier === 'large',
    // Se cornhub non risponde alla stima non si blocca: decide la chiamata vera.
    allowed: item ? item.allowed : true,
    message: item?.message ?? '',
    accountUrl: data?.account_url ?? '',
  }
}

/** Il simbolo dei bottoni delle funzioni grandi: "usa la tua chiave". */
export function AiKeyIcon({ size = 18 }: { size?: number }) {
  return (
    <span title={gettext('Usa la tua chiave API')} className="inline-flex">
      <Icon name="key" size={size} />
    </span>
  )
}
