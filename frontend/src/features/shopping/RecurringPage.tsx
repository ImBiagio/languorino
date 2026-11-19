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
import type {
  MealSlot,
  RecurringItem,
  RecurringPayload,
  RecurringSuggestion,
  Unit,
} from '../../lib/types'
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

/** Gli alimenti di colazione e merende del piano alimentare, da scegliere. */
function Suggestions() {
  const { data } = useRecurringSuggestions()
  const add = useAddRecurringItems()
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const groups = useMemo(() => {
    const out = new Map<MealSlot, RecurringSuggestion[]>()
    for (const item of data?.items ?? []) {
      if (!item.saved) out.set(item.slot, [...(out.get(item.slot) ?? []), item])
    }
    return [...out.entries()]
  }, [data])
  if (!data) return null
  const toggle = (key: string) => {
    const next = new Set(picked)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setPicked(next)
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
          {data.items.length
            ? gettext('Hai già aggiunto tutto quello che ti proponevo.')
            : gettext(
                'I pasti del piano sono già tutti nella preparazione: la spesa li prende da lì.',
              )}
        </p>
      ) : (
        <>
          <p className="mb-3 text-body-medium text-on-surface-variant">
            {interpolate(
              gettext(
                'Da “%s”, i pasti che non prepari. Le volte a settimana dividono i 7 giorni fra le opzioni: dopo puoi cambiarle.',
              ),
              [data.plan.title],
            )}
          </p>
          <div className="grid gap-3">
            {groups.map(([slot, items]) => {
              const all = items.every((item) => picked.has(item.key))
              return (
                <section key={slot} className="rounded-card bg-surface-container-low p-3">
                  <div className="mb-1 flex items-center gap-2 px-2">
                    <Icon name={SLOT_ICONS[slot]} size={22} className="text-primary" />
                    <h3 className="flex-1 text-title-medium">{SLOT_LABELS[slot]}</h3>
                    <button
                      type="button"
                      className="btn-text"
                      onClick={() => {
                        const next = new Set(picked)
                        for (const item of items) {
                          if (all) next.delete(item.key)
                          else next.add(item.key)
                        }
                        setPicked(next)
                      }}
                    >
                      {all ? gettext('Nessuno') : gettext('Tutti')}
                    </button>
                  </div>
                  <ul>
                    {items.map((item) => (
                      <li key={item.key}>
                        <button
                          type="button"
                          role="checkbox"
                          aria-checked={picked.has(item.key)}
                          onClick={() => toggle(item.key)}
                          className="state flex w-full items-center gap-3 rounded-row px-2 py-2 text-left"
                        >
                          <span
                            className={clsx(
                              'flex h-6 w-6 shrink-0 items-center justify-center rounded-[8px] border-2 transition',
                              picked.has(item.key)
                                ? 'border-primary bg-primary text-on-primary'
                                : 'border-outline',
                            )}
                          >
                            {picked.has(item.key) && <Icon name="check" size={18} />}
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
          <ErrorBanner error={add.error} />
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              className="btn-filled"
              disabled={!picked.size || add.isPending}
              onClick={async () => {
                const rows: Partial<RecurringPayload>[] = data.items
                  .filter((item) => picked.has(item.key))
                  .map(({ label, quantity, unit, times_per_week, slot }) => ({
                    label,
                    quantity,
                    unit,
                    times_per_week,
                    slot,
                  }))
                try {
                  await add.mutateAsync(rows)
                  setPicked(new Set())
                } catch {
                  // Errore sopra.
                }
              }}
            >
              <Icon name="add" size={20} />
              {interpolate(gettext('Aggiungi ai ricorrenti (%s)'), [picked.size])}
            </button>
          </div>
        </>
      )}
    </section>
  )
}
