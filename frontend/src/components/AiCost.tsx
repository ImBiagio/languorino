import { useAiQuote } from '../api/hooks'
import { gettext, interpolate } from '../lib/i18n'
import { Icon } from './ui'

/**
 * Accanto al bottone di una funzione AI grande: dice chi paga e quanto, prima
 * di premere (ADR 0021, come nel template).
 *
 * - piccola, sulla chiave di casa: "1 🌽" (pannocchie della quota del giorno);
 * - grande, con la chiave dell'utente: "~0,12 € con la tua chiave";
 * - non disponibile (serve la chiave, limite raggiunto): il motivo e il link
 *   a cornhub per aggiungere la chiave o alzare il limite.
 *
 * ``count``: quante volte l'azione chiama la funzione (es. 5 settimane di
 * piano, i pezzi di un ricettario). ``note``: una riga in piu' sotto la stima.
 */
export function AiCost({
  feature,
  count = 1,
  note,
}: {
  feature: string
  count?: number
  note?: string
}) {
  const n = Math.max(1, Math.round(count))
  const features = n > 1 ? [`${feature}:${n}`] : [feature]
  const { data } = useAiQuote(features)
  const item = data?.items[0]
  if (!item || !data) return null

  if (!item.allowed) {
    return (
      <p className="mt-2 flex items-start gap-2 rounded-row bg-surface-container p-3 text-body-small text-on-surface-variant">
        <Icon name="key" size={18} />
        <span>
          {item.message}{' '}
          <a className="text-primary underline" href={data.account_url}>
            {gettext('Apri cornhub')}
          </a>
        </span>
      </p>
    )
  }
  const badge =
    item.billed_to === 'house' ? (
      <span
        className="inline-flex items-center gap-1 text-body-small text-on-surface-variant"
        title={interpolate(gettext('Pannocchie rimaste oggi: %s'), [data.pannocchie_left])}
      >
        {/* Numero e pannocchia: niente da tradurre. */}
        {item.estimate_pannocchie ?? 1} 🌽
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 rounded-pill bg-tertiary-container px-2 py-0.5 text-label-small text-on-tertiary-container">
        <Icon name="key" size={14} />
        {interpolate(gettext('~%s con la tua chiave'), [item.estimate_label ?? ''])}
      </span>
    )
  if (!note) return badge
  return (
    <span className="inline-flex flex-col gap-0.5">
      {badge}
      <span className="text-body-small text-on-surface-variant">{note}</span>
    </span>
  )
}
