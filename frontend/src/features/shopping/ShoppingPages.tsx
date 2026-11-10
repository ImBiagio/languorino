// Lista della spesa (ADR 0008): generata dal piano o scritta a mano, divisa per
// reparto nell'ordine del supermercato, da spuntare con un tocco.

import clsx from 'clsx'
import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'

import {
  useAddShoppingItem,
  useCreateShoppingList,
  useCurrentPlan,
  useDeleteShoppingItem,
  useDeleteShoppingList,
  useRegenerateShoppingList,
  useShoppingList,
  useShoppingLists,
  useUpdateShoppingItem,
  useUpdateShoppingList,
} from '../../api/hooks'
import { useConfirm } from '../../components/ConfirmDialog'
import { Page } from '../../components/Layout'
import { EmptyPlateIllustration, FoodPattern } from '../../components/illustrations'
import {
  EmptyState,
  ErrorBanner,
  Icon,
  IconButton,
  Modal,
  Progress,
  Skeleton,
} from '../../components/ui'
import { gettext, interpolate, intlLocale, ngettext } from '../../lib/i18n'
import type { Category, MealPlan, ShoppingItem, ShoppingListDetail } from '../../lib/types'
import { addDays, formatRange, todayIso } from '../plans/dates'
import { CATEGORY_LABELS, unitLabel } from '../recipes/options'

const CATEGORY_ORDER: Category[] = [
  'produce',
  'meat',
  'fish',
  'dairy',
  'bakery',
  'pantry',
  'spices',
  'frozen',
  'drinks',
  'other',
]
const CATEGORY_ICONS: Record<Category, string> = {
  produce: 'nutrition',
  meat: 'kebab_dining',
  fish: 'set_meal',
  dairy: 'egg',
  bakery: 'bakery_dining',
  pantry: 'kitchen',
  spices: 'grain',
  frozen: 'ac_unit',
  drinks: 'local_bar',
  other: 'shopping_basket',
}

/** "1,2 kg", "350 g", "3 pz", "2 scatole"; vuoto senza quantita'. */
export function formatAmount(item: Pick<ShoppingItem, 'quantity' | 'unit'>): string {
  if (item.quantity === null || !item.unit) return ''
  let value = Number(item.quantity)
  let unit: string = item.unit
  if (unit === 'g' && value >= 1000) {
    value /= 1000
    unit = 'kg'
  } else if (unit === 'ml' && value >= 1000) {
    value /= 1000
    unit = 'l'
  }
  const number = new Intl.NumberFormat(intlLocale(), { maximumFractionDigits: 2 }).format(value)
  const label = ['g', 'kg', 'ml', 'l'].includes(unit) ? unit : unitLabel(item.unit, value)
  return `${number} ${label}`
}

/* -------------------------------------------------------------- /spesa ---- */

export function ShoppingHomePage() {
  const { data: lists } = useShoppingLists()
  const { data: plan } = useCurrentPlan()
  const [making, setMaking] = useState(false)
  const create = useCreateShoppingList()
  const navigate = useNavigate()
  if (!lists) return <Skeleton className="m-5 h-64 rounded-card md:m-8" />
  const open = lists.find((list) => list.status === 'open')
  if (open) return <Navigate to={`/spesa/${open.id}`} replace />
  const done = lists.filter((list) => list.status === 'done').slice(0, 5)

  return (
    <Page className="px-5 pt-5 md:px-8 md:pt-8">
      <h1 className="mb-4 text-[28px] font-medium leading-9 md:text-headline-small">
        {gettext('Spesa')}
      </h1>
      <EmptyState
        illustration={<EmptyPlateIllustration />}
        title={gettext('Nessuna lista aperta')}
        description={
          plan
            ? gettext('Calcolo io cosa comprare dal tuo piano, già diviso per reparto.')
            : gettext('Scrivi una lista a mano, o crea un piano e la calcolo io.')
        }
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <button
              type="button"
              className={plan ? 'btn-outlined' : 'btn-filled'}
              disabled={create.isPending}
              onClick={async () => {
                const list = await create.mutateAsync({})
                navigate(`/spesa/${list.id}`)
              }}
            >
              <Icon name="edit_note" size={20} />
              {gettext('Lista vuota')}
            </button>
            {plan && (
              <button type="button" className="btn-filled" onClick={() => setMaking(true)}>
                <Icon name="shopping_cart" size={20} />
                {gettext('Dal piano')}
              </button>
            )}
          </div>
        }
      />
      <ErrorBanner error={create.error} />
      {done.length > 0 && (
        <section className="mt-6">
          <h2 className="mb-2 text-title-medium">{gettext('Liste fatte')}</h2>
          <ul className="grid gap-2">
            {done.map((list) => (
              <li key={list.id}>
                <Link
                  to={`/spesa/${list.id}`}
                  className="state flex items-center gap-3 rounded-row bg-surface-container-low px-4 py-3"
                >
                  <Icon name="task_alt" size={22} className="text-success" />
                  <span className="min-w-0 flex-1 truncate text-body-large">{list.title}</span>
                  <Icon name="chevron_right" size={22} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      {making && plan && <MakeShoppingDialog plan={plan} onClose={() => setMaking(false)} />}
    </Page>
  )
}

/**
 * "Fai la spesa" dal piano: per quali giorni. Le scelte partono da oggi (o
 * dall'inizio del piano, se non e' ancora cominciato).
 */
export function MakeShoppingDialog({ plan, onClose }: { plan: MealPlan; onClose: () => void }) {
  const navigate = useNavigate()
  const create = useCreateShoppingList()
  const today = todayIso()
  const from = today > plan.start_date ? today : plan.start_date
  const options = [
    { days: 3, label: gettext('Prossimi 3 giorni') },
    { days: 7, label: gettext('Una settimana') },
    { days: 0, label: gettext('Fino alla fine del piano') },
  ]
  const make = async (days: number) => {
    const to = days ? addDays(from, days - 1) : plan.end_date
    try {
      const list = await create.mutateAsync({
        plan: plan.id,
        date_from: from,
        date_to: to > plan.end_date ? plan.end_date : to,
      })
      navigate(`/spesa/${list.id}`)
    } catch {
      // Errore nel dialog.
    }
  }
  return (
    <Modal open onClose={onClose} title={gettext('Per quali giorni fai la spesa?')}>
      <div className="grid gap-2">
        {options.map((option) => {
          const to = option.days ? addDays(from, option.days - 1) : plan.end_date
          return (
            <button
              key={option.days}
              type="button"
              disabled={create.isPending}
              onClick={() => make(option.days)}
              className="state flex items-center gap-3 rounded-row bg-surface-container-low px-4 py-3 text-left"
            >
              <Icon name="date_range" size={22} className="text-primary" />
              <span className="min-w-0 flex-1">
                <span className="block text-body-large font-medium">{option.label}</span>
                <span className="block text-body-small text-on-surface-variant">
                  {formatRange(from, to > plan.end_date ? plan.end_date : to)}
                </span>
              </span>
              <Icon name="chevron_right" size={22} />
            </button>
          )
        })}
        <ErrorBanner error={create.error} />
      </div>
    </Modal>
  )
}

/* ---------------------------------------------------------- /spesa/:id ---- */

export function ShoppingPage() {
  const { listId } = useParams()
  const { data: list, error } = useShoppingList(listId)
  if (error) {
    return (
      <Page className="px-5 pt-5 md:px-8 md:pt-8">
        <ErrorBanner error={error} />
      </Page>
    )
  }
  if (!list) return <Skeleton className="m-5 h-72 rounded-card md:m-8" />
  return <ShoppingView list={list} />
}

function ShoppingView({ list }: { list: ShoppingListDetail }) {
  const navigate = useNavigate()
  const confirm = useConfirm()
  const update = useUpdateShoppingList()
  const regenerate = useRegenerateShoppingList()
  const remove = useDeleteShoppingList()
  const [showPantry, setShowPantry] = useState(false)
  const toBuy = list.items.filter((item) => !item.in_pantry)
  const pantry = list.items.filter((item) => item.in_pantry)
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    // Le spuntate in fondo al reparto: in alto resta quello che manca.
    items: toBuy
      .filter((item) => item.category === category)
      .sort((a, b) => Number(a.checked) - Number(b.checked)),
  })).filter((group) => group.items.length)
  const done = list.status === 'done'

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="relative mb-4 overflow-hidden rounded-panel bg-primary px-5 py-5 text-on-primary md:px-7">
        <FoodPattern tone="dark" opacity={0.3} />
        <div className="relative flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-body-medium opacity-90">
              {done ? gettext('Spesa fatta') : gettext('Lista della spesa')}
            </p>
            <h1 className="truncate text-[24px] font-medium leading-8">{list.title}</h1>
            <p className="mt-1 text-body-small opacity-90">
              {interpolate(gettext('%s di %s nel carrello'), [list.checked_count, list.item_count])}
            </p>
            <div className="mt-2 max-w-xs [&_.progress]:bg-white/30 [&_.progress>span]:bg-white">
              <Progress
                value={list.checked_count}
                max={Math.max(list.item_count, 1)}
                label={gettext('Nel carrello')}
              />
            </div>
          </div>
          <div className="flex gap-1">
            {list.plan && (
              <IconButton
                icon="refresh"
                size="md"
                inheritColor
                label={gettext('Ricalcola dal piano')}
                disabled={regenerate.isPending}
                onClick={() => regenerate.mutate(list.id)}
              />
            )}
            <IconButton
              icon="delete"
              size="md"
              inheritColor
              label={gettext('Elimina la lista')}
              onClick={async () => {
                const ok = await confirm({
                  title: gettext('Eliminare la lista?'),
                  confirmLabel: gettext('Elimina'),
                  icon: 'delete',
                  destructive: true,
                })
                if (!ok) return
                await remove.mutateAsync(list.id)
                navigate('/spesa', { replace: true })
              }}
            />
          </div>
        </div>
      </header>
      <ErrorBanner error={update.error ?? regenerate.error ?? remove.error} />

      <AddItem listId={list.id} />

      {!toBuy.length && <EmptyState icon="shopping_basket" title={gettext('Niente da comprare')} />}
      <div className="mt-4 grid gap-3">
        {groups.map((group) => (
          <section key={group.category} className="rounded-card bg-surface-container-low p-3">
            <h2 className="mb-1 flex items-center gap-2 px-2 text-title-medium">
              <Icon name={CATEGORY_ICONS[group.category]} size={22} className="text-primary" />
              {CATEGORY_LABELS[group.category]}
            </h2>
            <ul>
              {group.items.map((item) => (
                <ItemRow key={item.id} listId={list.id} item={item} />
              ))}
            </ul>
          </section>
        ))}
      </div>

      {pantry.length > 0 && (
        <section className="mt-3 rounded-card bg-surface-container-low p-3">
          <button
            type="button"
            className="flex w-full items-center gap-2 px-2 py-1 text-left"
            onClick={() => setShowPantry(!showPantry)}
            aria-expanded={showPantry}
          >
            <Icon name="kitchen" size={22} className="text-on-surface-variant" />
            <span className="flex-1 text-title-medium">
              {interpolate(gettext('Ce l’ho già (%s)'), [pantry.length])}
            </span>
            <Icon name={showPantry ? 'expand_less' : 'expand_more'} size={22} />
          </button>
          {showPantry && (
            <ul className="mt-1">
              {pantry.map((item) => (
                <ItemRow key={item.id} listId={list.id} item={item} />
              ))}
            </ul>
          )}
        </section>
      )}

      <div className="mt-5 flex flex-wrap justify-end gap-2">
        {done ? (
          <button
            type="button"
            className="btn-outlined"
            onClick={() => update.mutate({ id: list.id, status: 'open' })}
          >
            {gettext('Riapri la lista')}
          </button>
        ) : (
          <button
            type="button"
            className="btn-filled"
            onClick={() => update.mutate({ id: list.id, status: 'done' })}
          >
            <Icon name="task_alt" size={20} />
            {gettext('Spesa fatta')}
          </button>
        )}
      </div>
    </Page>
  )
}

function AddItem({ listId }: { listId: string }) {
  const add = useAddShoppingItem(listId)
  const [text, setText] = useState('')
  return (
    <form
      className="flex items-center gap-2"
      onSubmit={async (event) => {
        event.preventDefault()
        const label = text.trim()
        if (!label) return
        try {
          await add.mutateAsync({ label })
          setText('')
        } catch {
          // Errore sotto.
        }
      }}
    >
      <label className="flex min-w-0 flex-1 items-center gap-3 rounded-pill bg-surface-container-high px-5 py-3 focus-within:ring-2 focus-within:ring-primary">
        <Icon name="add_shopping_cart" size={22} className="text-on-surface-variant" />
        <input
          className="min-w-0 flex-1 bg-transparent text-body-large outline-none placeholder:text-on-surface-variant"
          placeholder={gettext('Aggiungi qualcosa (es. detersivo, pane)')}
          value={text}
          maxLength={120}
          onChange={(event) => setText(event.target.value)}
        />
      </label>
      <button className="btn-tonal" disabled={!text.trim() || add.isPending}>
        {gettext('Aggiungi')}
      </button>
      <ErrorBanner error={add.error} />
    </form>
  )
}

function ItemRow({ listId, item }: { listId: string; item: ShoppingItem }) {
  const update = useUpdateShoppingItem(listId)
  const remove = useDeleteShoppingItem(listId)
  const [editing, setEditing] = useState(false)
  const amount = formatAmount(item)
  const recipes = [...new Set(item.sources.map((source) => source.recipe))]
  return (
    <li className="flex items-center gap-2 py-1">
      <button
        type="button"
        role="checkbox"
        aria-checked={item.checked}
        onClick={() => update.mutate({ id: item.id, checked: !item.checked })}
        className="state flex min-w-0 flex-1 items-center gap-3 rounded-row px-2 py-2 text-left"
      >
        <span
          className={clsx(
            'flex h-6 w-6 shrink-0 items-center justify-center rounded-[8px] border-2 transition',
            item.checked ? 'border-primary bg-primary text-on-primary' : 'border-outline',
          )}
        >
          {item.checked && <Icon name="check" size={18} />}
        </span>
        <span className="min-w-0 flex-1">
          <span
            className={clsx(
              'block truncate text-body-large',
              item.checked && 'text-on-surface-variant line-through',
            )}
          >
            {item.label}
          </span>
          {recipes.length > 0 && (
            <span className="block truncate text-body-small text-on-surface-variant">
              {interpolate(gettext('per %s'), [recipes.join(', ')])}
            </span>
          )}
        </span>
        <span className="amount shrink-0 text-body-medium text-on-surface-variant">
          {amount || (item.manual ? '' : gettext('q.b.'))}
        </span>
      </button>
      <IconButton
        icon={item.in_pantry ? 'add_shopping_cart' : 'kitchen'}
        label={item.in_pantry ? gettext('Da comprare') : gettext('Ce l’ho già')}
        onClick={() => update.mutate({ id: item.id, in_pantry: !item.in_pantry })}
      />
      <IconButton
        icon="edit"
        label={gettext('Modifica la voce')}
        onClick={() => setEditing(true)}
      />
      {editing && (
        <EditItemDialog
          item={item}
          onClose={() => setEditing(false)}
          onSave={async (changes) => {
            await update.mutateAsync({ id: item.id, ...changes })
            setEditing(false)
          }}
          onDelete={async () => {
            await remove.mutateAsync(item.id)
            setEditing(false)
          }}
        />
      )}
    </li>
  )
}

function EditItemDialog({
  item,
  onClose,
  onSave,
  onDelete,
}: {
  item: ShoppingItem
  onClose: () => void
  onSave: (changes: Partial<ShoppingItem>) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const [label, setLabel] = useState(item.label)
  const [quantity, setQuantity] = useState(
    item.quantity === null ? '' : String(Number(item.quantity)),
  )
  const [error, setError] = useState<unknown>(null)
  return (
    <Modal open onClose={onClose} title={gettext('Modifica la voce')}>
      <form
        className="grid gap-4"
        onSubmit={async (event) => {
          event.preventDefault()
          try {
            const value = quantity.replace(',', '.').trim()
            await onSave({ label, quantity: value || null })
          } catch (err) {
            setError(err)
          }
        }}
      >
        <label className="field block">
          <span className="field-label">{gettext('Cosa')}</span>
          <input
            className="field-input"
            value={label}
            maxLength={120}
            onChange={(e) => setLabel(e.target.value)}
          />
        </label>
        <label className="field block">
          <span className="field-label">
            {item.unit
              ? interpolate(gettext('Quantità (%s)'), [
                  item.unit === 'g' || item.unit === 'ml' ? item.unit : unitLabel(item.unit, 2),
                ])
              : gettext('Quantità')}
          </span>
          <input
            className="field-input"
            inputMode="decimal"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value.replace(/[^\d.,]/g, ''))}
          />
        </label>
        {item.sources.length > 0 && (
          <p className="text-body-small text-on-surface-variant">
            {interpolate(
              ngettext(
                'Serve per %s pasto del piano.',
                'Serve per %s pasti del piano.',
                item.sources.length,
              ),
              [item.sources.length],
            )}{' '}
            {gettext('Se la cambi, ricalcolando dal piano resta com’è.')}
          </p>
        )}
        <ErrorBanner error={error} />
        <div className="flex justify-between gap-2">
          <button type="button" className="btn-text text-error" onClick={onDelete}>
            <Icon name="delete" size={20} />
            {gettext('Togli')}
          </button>
          <div className="flex gap-2">
            <button type="button" className="btn-text" onClick={onClose}>
              {gettext('Annulla')}
            </button>
            <button className="btn-filled" disabled={!label.trim()}>
              {gettext('Salva')}
            </button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
