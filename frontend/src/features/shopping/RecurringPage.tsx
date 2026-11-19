// I ricorrenti della spesa (ADR 0024): cose che si comprano sempre, anche se
// la preparazione non le mette nei giorni (la colazione tolta dal piano, il
// caffè, il detersivo). Qui si scelgono; la spesa li aggiunge per i giorni
// della lista. I suggerimenti vengono dai pasti del piano alimentare che la
// preparazione non prepara.

import clsx from 'clsx'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  useAddRecurringItems,
  useDeleteRecurringItem,
  useRecurringItems,
  useRecurringSuggestions,
  useUpdateRecurringItem,
} from '../../api/hooks'
import { Page } from '../../components/Layout'
import {
  EmptyState,
  ErrorBanner,
  Icon,
  IconButton,
  Modal,
  RowsSkeleton,
  Stepper,
  Switch,
} from '../../components/ui'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { MealSlot, RecurringItem, RecurringSuggestion, Unit } from '../../lib/types'
import { MEAL_OPTIONS } from '../profile/options'
import { UNIT_OPTIONS, unitLabel } from '../recipes/options'
import { formatAmount } from './ShoppingPages'

const SLOT_LABELS = Object.fromEntries(MEAL_OPTIONS.map((option) => [option.value, option.label]))
const SLOT_ICONS = Object.fromEntries(MEAL_OPTIONS.map((option) => [option.value, option.icon]))

/** "ogni giorno", "4 volte a settimana". */
export function timesLabel(times: number): string {
  if (times === 7) return gettext('ogni giorno')
  return interpolate(ngettext('%s volta a settimana', '%s volte a settimana', times), [times])
}

/** "200 g · 4 volte a settimana"; senza quantità solo le volte. */
function describe(item: Pick<RecurringItem, 'quantity' | 'unit' | 'times_per_week'>): string {
  const amount = formatAmount(item)
  return amount ? `${amount} · ${timesLabel(item.times_per_week)}` : gettext('Da comprare sempre')
}

export function RecurringPage() {
  const navigate = useNavigate()
  const { data: items, error } = useRecurringItems()
  const add = useAddRecurringItems()
  const [text, setText] = useState('')

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="mb-4 flex items-center gap-3">
        <IconButton
          icon="arrow_back"
          size="md"
          label={gettext('Spesa')}
          onClick={() => navigate(-1)}
        />
        <h1 className="flex-1 text-title-large">{gettext('Ricorrenti')}</h1>
      </header>
      <p className="mb-4 max-w-2xl text-body-medium text-on-surface-variant">
        {gettext(
          'Le cose che compri sempre, anche se non sono nei pasti preparati: la colazione, le merende, il caffè, il detersivo. Le aggiungo alla spesa per i giorni della lista, insieme a quello che serve per il piano.',
        )}
      </p>
      <ErrorBanner error={error} />

      <form
        className="mb-4 flex items-center gap-2"
        onSubmit={async (event) => {
          event.preventDefault()
          const label = text.trim()
          if (!label) return
          try {
            await add.mutateAsync([{ label }])
            setText('')
          } catch {
            // Errore sotto.
          }
        }}
      >
        <label className="flex min-w-0 flex-1 items-center gap-3 rounded-pill bg-surface-container-high px-5 py-3 focus-within:ring-2 focus-within:ring-primary">
          <Icon name="event_repeat" size={22} className="text-on-surface-variant" />
          <input
            className="min-w-0 flex-1 bg-transparent text-body-large outline-none placeholder:text-on-surface-variant"
            placeholder={gettext('Aggiungi (es. caffè, detersivo)')}
            value={text}
            maxLength={120}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <button className="btn-tonal" disabled={!text.trim() || add.isPending}>
          {gettext('Aggiungi')}
        </button>
      </form>
      <ErrorBanner error={add.error} />

      {!items ? (
        <RowsSkeleton rows={3} />
      ) : items.length ? (
        <ul className="grid gap-1 rounded-card bg-surface-container-low p-2">
          {items.map((item) => (
            <RecurringRow key={item.id} item={item} />
          ))}
        </ul>
      ) : (
        <EmptyState
          icon="event_repeat"
          title={gettext('Nessun ricorrente')}
          description={gettext('Scrivine uno sopra o sceglili dal tuo piano alimentare qui sotto.')}
        />
      )}

      <Suggestions />
    </Page>
  )
}

function RecurringRow({ item }: { item: RecurringItem }) {
  const update = useUpdateRecurringItem()
  const remove = useDeleteRecurringItem()
  const [editing, setEditing] = useState(false)
  return (
    <li className="flex items-center gap-3 px-2 py-2">
      <Switch
        checked={item.active}
        label={item.active ? gettext('Togli dalla spesa') : gettext('Metti in spesa')}
        onChange={(active) => update.mutate({ id: item.id, active })}
      />
      <button
        type="button"
        className={clsx(
          'state min-w-0 flex-1 rounded-row px-2 py-1 text-left',
          !item.active && 'opacity-60',
        )}
        onClick={() => setEditing(true)}
      >
        <span className="block truncate text-body-large">{item.label}</span>
        <span className="block truncate text-body-small text-on-surface-variant">
          {item.slot ? `${SLOT_LABELS[item.slot]} · ` : ''}
          {describe(item)}
        </span>
      </button>
      <IconButton icon="edit" label={gettext('Modifica')} onClick={() => setEditing(true)} />
      <IconButton
        icon="close"
        label={interpolate(gettext('Togli “%s” dai ricorrenti'), [item.label])}
        disabled={remove.isPending}
        onClick={() => remove.mutate(item.id)}
      />
      {editing && <EditRecurringDialog item={item} onClose={() => setEditing(false)} />}
    </li>
  )
}

const EDIT_UNITS: Unit[] = UNIT_OPTIONS.filter((unit) => unit !== 'to_taste')

function EditRecurringDialog({ item, onClose }: { item: RecurringItem; onClose: () => void }) {
  const update = useUpdateRecurringItem()
  const remove = useDeleteRecurringItem()
  const [label, setLabel] = useState(item.label)
  const [quantity, setQuantity] = useState(
    item.quantity === null ? '' : String(Number(item.quantity)),
  )
  const [unit, setUnit] = useState<Unit>(item.unit || 'g')
  const [times, setTimes] = useState(item.times_per_week)
  return (
    <Modal open onClose={onClose} title={gettext('Modifica il ricorrente')}>
      <form
        className="grid gap-4"
        onSubmit={async (event) => {
          event.preventDefault()
          const value = quantity.replace(',', '.').trim()
          try {
            await update.mutateAsync({
              id: item.id,
              label,
              quantity: value || null,
              unit: value ? unit : '',
              times_per_week: times,
            })
            onClose()
          } catch {
            // Errore sotto.
          }
        }}
      >
        <label className="field block">
          <span className="field-label">{gettext('Cosa')}</span>
          <input
            className="field-input"
            value={label}
            maxLength={120}
            onChange={(event) => setLabel(event.target.value)}
          />
        </label>
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <label className="field block">
            <span className="field-label">{gettext('Quantità per volta')}</span>
            <input
              className="field-input"
              inputMode="decimal"
              placeholder={gettext('Facoltativa')}
              value={quantity}
              onChange={(event) => setQuantity(event.target.value.replace(/[^\d.,]/g, ''))}
            />
          </label>
          <label className="field block">
            <span className="field-label">{gettext('Unità')}</span>
            <select
              className="field-input"
              value={unit}
              onChange={(event) => setUnit(event.target.value as Unit)}
            >
              {EDIT_UNITS.map((option) => (
                <option key={option} value={option}>
                  {unitLabel(option, 2)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-body-large">{gettext('Volte a settimana')}</span>
          <Stepper
            value={times}
            onChange={setTimes}
            min={1}
            max={21}
            label={gettext('Volte a settimana')}
          />
        </div>
        <p className="text-body-small text-on-surface-variant">
          {gettext(
            'La quantità è per tutta la casa. Per una spesa di 3 giorni conto 3/7 delle volte, per due settimane il doppio.',
          )}
        </p>
        <ErrorBanner error={update.error ?? remove.error} />
        <div className="flex justify-between gap-2">
          <button
            type="button"
            className="btn-text text-error"
            onClick={async () => {
              await remove.mutateAsync(item.id)
              onClose()
            }}
          >
            <Icon name="delete" size={20} />
            {gettext('Elimina')}
          </button>
          <div className="flex gap-2">
            <button type="button" className="btn-text" onClick={onClose}>
              {gettext('Annulla')}
            </button>
            <button className="btn-filled" disabled={!label.trim() || update.isPending}>
              {gettext('Salva')}
            </button>
          </div>
        </div>
      </form>
    </Modal>
  )
}

/** Gli alimenti di colazione e merende del piano alimentare: la spunta li
 * aggiunge o li toglie subito dai ricorrenti, senza un passo di conferma. */
function Suggestions() {
  const { data } = useRecurringSuggestions()
  const add = useAddRecurringItems()
  const remove = useDeleteRecurringItem()
  // Le righe in corso, perché la spunta non scatti due volte prima della risposta.
  const [busy, setBusy] = useState<Set<string>>(new Set())
  const groups = useMemo(() => {
    const out = new Map<MealSlot, RecurringSuggestion[]>()
    for (const item of data?.items ?? []) {
      out.set(item.slot, [...(out.get(item.slot) ?? []), item])
    }
    return [...out.entries()]
  }, [data])
  if (!data) return null

  /** Mette (on) o toglie (off) dai ricorrenti un gruppo di suggerimenti. */
  const apply = async (items: RecurringSuggestion[], on: boolean) => {
    const todo = items.filter((item) => item.saved !== on && !busy.has(item.key))
    if (!todo.length) return
    const keys = todo.map((item) => item.key)
    setBusy((current) => new Set([...current, ...keys]))
    try {
      if (on) {
        await add.mutateAsync(
          todo.map(({ label, quantity, unit, times_per_week, slot }) => ({
            label,
            quantity,
            unit,
            times_per_week,
            slot,
          })),
        )
      } else {
        // Lo stesso alimento può stare in due pasti: un ricorrente si toglie una volta.
        const ids = new Set(todo.map((item) => item.saved_id).filter((id) => id !== null))
        await Promise.all([...ids].map((id) => remove.mutateAsync(id)))
      }
    } catch {
      // Errore sotto.
    } finally {
      setBusy((current) => new Set([...current].filter((key) => !keys.includes(key))))
    }
  }

  return (
    <section className="mt-6">
      <h2 className="mb-1 text-title-medium">{gettext('Dal tuo piano alimentare')}</h2>
      {!data.plan ? (
        <p className="text-body-medium text-on-surface-variant">
          {gettext(
            'Con un piano alimentare confermato ti propongo qui gli alimenti di colazione e merende.',
          )}
        </p>
      ) : !groups.length ? (
        <p className="text-body-medium text-on-surface-variant">
          {gettext(
            'I pasti del piano sono già tutti nella preparazione: la spesa li prende da lì.',
          )}
        </p>
      ) : (
        <>
          <p className="mb-3 text-body-medium text-on-surface-variant">
            {interpolate(
              gettext(
                'Da “%s”, i pasti che non prepari. Spunta per aggiungere ai ricorrenti, togli la spunta per levarlo. Le volte a settimana dividono i 7 giorni fra le opzioni: dopo puoi cambiarle.',
              ),
              [data.plan.title],
            )}
          </p>
          <ErrorBanner error={add.error ?? remove.error} />
          <div className="grid gap-3">
            {groups.map(([slot, items]) => {
              const all = items.every((item) => item.saved)
              return (
                <section key={slot} className="rounded-card bg-surface-container-low p-3">
                  <div className="mb-1 flex items-center gap-2 px-2">
                    <Icon name={SLOT_ICONS[slot]} size={22} className="text-primary" />
                    <h3 className="flex-1 text-title-medium">{SLOT_LABELS[slot]}</h3>
                    <button
                      type="button"
                      className="btn-text"
                      disabled={items.some((item) => busy.has(item.key))}
                      onClick={() => apply(items, !all)}
                    >
                      {all ? gettext('Togli tutti') : gettext('Aggiungi tutti')}
                    </button>
                  </div>
                  <ul>
                    {items.map((item) => (
                      <li key={item.key}>
                        <button
                          type="button"
                          role="checkbox"
                          aria-checked={item.saved}
                          disabled={busy.has(item.key)}
                          onClick={() => apply([item], !item.saved)}
                          className="state flex w-full items-center gap-3 rounded-row px-2 py-2 text-left disabled:opacity-60"
                        >
                          <span
                            className={clsx(
                              'flex h-6 w-6 shrink-0 items-center justify-center rounded-[8px] border-2 transition',
                              item.saved
                                ? 'border-primary bg-primary text-on-primary'
                                : 'border-outline',
                            )}
                          >
                            {item.saved && <Icon name="check" size={18} />}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-body-large">{item.label}</span>
                            <span className="block truncate text-body-small text-on-surface-variant">
                              {item.quantity ? describe(item) : item.option}
                            </span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              )
            })}
          </div>
        </>
      )}
    </section>
  )
}
