import clsx from 'clsx'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'

import {
  useActivatePlan,
  useBooks,
  useCurrentPlan,
  useDeletePlan,
  useJob,
  useMealIdeas,
  usePlan,
  usePlans,
  useRecipes,
  useRegeneratePlan,
  useRetryPlan,
  useUpdateMeal,
} from '../../api/hooks'
import { useConfirm } from '../../components/ConfirmDialog'
import { Page } from '../../components/Layout'
import {
  CookbookIllustration,
  EmptyPlateIllustration,
  FoodPattern,
  RecipeCover,
} from '../../components/illustrations'
import {
  Chip,
  EmptyState,
  ErrorBanner,
  Field,
  Icon,
  IconButton,
  Modal,
  Progress,
  Segmented,
  Skeleton,
  Stepper,
} from '../../components/ui'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type {
  MealPlanDetail,
  PlannedMeal,
  PortionLine,
  RecipeBook,
  RecipeSummary,
} from '../../lib/types'
import { MEAL_OPTIONS } from '../profile/options'
import { formatMinutes, formatQuantity } from '../recipes/options'
import { MakeShoppingDialog } from '../shopping/ShoppingPages'
import {
  addDays,
  formatDayLong,
  formatDayShort,
  formatRange,
  formatWeekday,
  todayIso,
} from './dates'
import { PREP_OPTIONS } from './options'

const SLOT_ORDER = MEAL_OPTIONS.map((option) => option.value)

/* -------------------------------------------------------------- /piano ---- */

/**
 * La voce "Piano": apre il piano in lavorazione o da attivare, se c'e',
 * altrimenti quello attivo; senza piani, l'invito a crearne uno.
 */
export function PlanHomePage() {
  const { data: plans } = usePlans()
  const { data: current, isPending } = useCurrentPlan()
  if (!plans || isPending) return <Skeleton className="m-5 h-64 rounded-card md:m-8" />
  const pending = plans.find((plan) => ['generating', 'draft', 'failed'].includes(plan.status))
  const target = pending ?? current
  if (target) return <Navigate to={`/piano/${target.id}`} replace />
  return (
    <Page className="px-5 pt-5 md:px-8 md:pt-8">
      <h1 className="mb-4 text-[28px] font-medium leading-9 md:text-headline-small">
        {gettext('Piano')}
      </h1>
      <EmptyState
        illustration={<EmptyPlateIllustration />}
        title={gettext('Ancora nessun piano')}
        description={gettext(
          'Componi la settimana dalle tue ricette e dai ricettari PDF, con il meal prep che preferisci.',
        )}
        action={
          <Link to="/piano/nuovo" className="btn-filled">
            <Icon name="auto_awesome" size={20} />
            {gettext('Crea il piano')}
          </Link>
        }
      />
      <NutritionistLink />
    </Page>
  )
}

/** Ingresso al piano del nutrizionista, sotto il piano. */
function NutritionistLink() {
  return (
    <Link
      to="/piano/nutrizionista"
      className="state mt-4 flex items-center gap-4 rounded-card bg-surface-container-low p-4"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-primary-container text-on-primary-container">
        <Icon name="clinical_notes" size={24} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-body-large font-medium">
          {gettext('Piano del nutrizionista')}
        </span>
        <span className="block text-body-small text-on-surface-variant">
          {gettext('Caricalo in PDF o foto e genero le settimane seguendolo')}
        </span>
      </span>
      <Icon name="chevron_right" size={22} />
    </Link>
  )
}

/* ---------------------------------------------------------- /piano/:id ---- */

export function PlanPage() {
  const { planId } = useParams()
  const { data: plan, error } = usePlan(planId)
  if (error) {
    return (
      <Page className="px-5 pt-5 md:px-8 md:pt-8">
        <ErrorBanner error={error} />
      </Page>
    )
  }
  if (!plan) return <Skeleton className="m-5 h-72 rounded-card md:m-8" />
  return <PlanView plan={plan} />
}

function PlanView({ plan }: { plan: MealPlanDetail }) {
  const navigate = useNavigate()
  const confirm = useConfirm()
  const activate = useActivatePlan()
  const regenerate = useRegeneratePlan()
  const retry = useRetryPlan()
  const remove = useDeletePlan()
  const [view, setView] = useState<'eat' | 'cook'>('eat')
  const [shopping, setShopping] = useState(false)
  const today = todayIso()
  const days = useMemo(
    () => Array.from({ length: plan.days }, (_, offset) => addDays(plan.start_date, offset)),
    [plan.start_date, plan.days],
  )
  // La settimana che contiene oggi, se c'e'; altrimenti la prima.
  const [week, setWeek] = useState(() => {
    const index = days.indexOf(today)
    return index >= 0 ? Math.floor(index / 7) : 0
  })
  const weekDays = days.slice(week * 7, week * 7 + 7)
  const prep = PREP_OPTIONS.find((option) => option.value === plan.settings.prep_mode)
  const mutationError = activate.error ?? regenerate.error ?? retry.error ?? remove.error

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="relative mb-4 overflow-hidden rounded-panel bg-primary px-5 py-5 text-on-primary md:px-7">
        <FoodPattern tone="dark" opacity={0.3} />
        <div className="relative flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-body-medium opacity-90">
              {plan.status === 'active'
                ? gettext('Il tuo piano')
                : plan.status === 'draft'
                  ? gettext('Bozza da attivare')
                  : plan.status === 'archived'
                    ? gettext('Piano archiviato')
                    : gettext('Piano in preparazione')}
            </p>
            <h1 className="text-[26px] font-medium leading-8">
              {formatRange(plan.start_date, plan.end_date)}
            </h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 text-body-small opacity-90">
              <span className="inline-flex items-center gap-1">
                <Icon name={prep?.icon ?? 'kitchen'} size={16} />
                {prep?.label}
              </span>
              {plan.nutritionist && (
                <Link
                  to={`/piano/nutrizionista/${plan.nutritionist.id}`}
                  className="inline-flex items-center gap-1 underline-offset-2 hover:underline"
                >
                  <Icon name="clinical_notes" size={16} />
                  {plan.nutritionist.title}
                </Link>
              )}
              <span className="inline-flex items-center gap-1">
                <Icon name="group" size={16} />
                {interpolate(ngettext('%s porzione', '%s porzioni', plan.settings.servings), [
                  plan.settings.servings,
                ])}
              </span>
            </p>
          </div>
          <div className="flex gap-1">
            {(plan.status === 'active' || plan.status === 'draft') && (
              <IconButton
                icon="shopping_cart"
                size="md"
                inheritColor
                label={gettext('Fai la spesa')}
                onClick={() => setShopping(true)}
              />
            )}
            <IconButton
              icon="add"
              size="md"
              inheritColor
              label={gettext('Nuovo piano')}
              onClick={() => navigate('/piano/nuovo')}
            />
            <IconButton
              icon="delete"
              size="md"
              inheritColor
              label={gettext('Elimina il piano')}
              onClick={async () => {
                const ok = await confirm({
                  title: gettext('Eliminare il piano?'),
                  message: gettext(
                    'Spariscono i pasti e le ricette scritte per il piano che non hai salvato.',
                  ),
                  confirmLabel: gettext('Elimina'),
                  icon: 'delete',
                  destructive: true,
                })
                if (!ok) return
                await remove.mutateAsync(plan.id)
                navigate('/piano', { replace: true })
              }}
            />
          </div>
        </div>
      </header>

      <ErrorBanner error={mutationError} />
      {shopping && <MakeShoppingDialog plan={plan} onClose={() => setShopping(false)} />}

      {plan.status === 'generating' && <Generating plan={plan} />}

      {plan.status === 'failed' && (
        <section className="mb-4 grid gap-3 rounded-card bg-surface-container-low p-5">
          <ErrorBanner error={plan.error || gettext('La preparazione si è interrotta.')} />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-filled"
              disabled={retry.isPending}
              onClick={() => retry.mutate(plan.id)}
            >
              <Icon name="refresh" size={20} />
              {gettext('Riprendi')}
            </button>
            <button
              type="button"
              className="btn-outlined"
              disabled={regenerate.isPending}
              onClick={() => regenerate.mutate(plan.id)}
            >
              {gettext('Rifai da capo')}
            </button>
          </div>
        </section>
      )}

      {plan.status === 'draft' && (
        <section className="mb-4 flex flex-wrap items-center gap-3 rounded-card bg-tertiary-container p-4 text-on-tertiary-container">
          <Icon name="rate_review" size={24} />
          <p className="min-w-0 flex-1 text-body-medium">
            {gettext(
              'Controlla i pasti e cambia quelli che non ti convincono, poi attiva il piano: comparirà in “Oggi”.',
            )}
          </p>
          <button
            type="button"
            className="btn-outlined btn-sm"
            disabled={regenerate.isPending}
            onClick={async () => {
              const ok = await confirm({
                title: gettext('Rifare il piano?'),
                message: gettext('Ricompongo tutte le settimane con le stesse scelte.'),
                confirmLabel: gettext('Rifai'),
                icon: 'refresh',
              })
              if (ok) regenerate.mutate(plan.id)
            }}
          >
            <Icon name="refresh" size={18} />
            {gettext('Rifai')}
          </button>
          <button
            type="button"
            className="btn-filled btn-sm"
            disabled={activate.isPending}
            onClick={() => activate.mutate(plan.id)}
          >
            <Icon name="check" size={18} />
            {gettext('Attiva il piano')}
          </button>
        </section>
      )}

      {plan.meals.length > 0 && (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <Segmented
              value={view}
              onChange={setView}
              options={[
                { value: 'eat', label: gettext('Cosa mangi') },
                { value: 'cook', label: gettext('Cosa cucini') },
              ]}
            />
            {plan.weeks_total > 1 && (
              <div className="no-scrollbar flex gap-2 overflow-x-auto">
                {Array.from({ length: plan.weeks_total }, (_, index) => (
                  <Chip
                    key={index}
                    label={interpolate(gettext('Settimana %s'), [index + 1])}
                    selected={week === index}
                    onClick={() => setWeek(index)}
                  />
                ))}
              </div>
            )}
          </div>
          {view === 'eat' ? (
            <EatView plan={plan} days={weekDays} today={today} />
          ) : (
            <CookView plan={plan} days={weekDays} today={today} />
          )}
        </>
      )}
      <NutritionistLink />
    </Page>
  )
}

function Generating({ plan }: { plan: MealPlanDetail }) {
  return (
    <EmptyState
      illustration={
        <div className="relative">
          <CookbookIllustration />
          <span className="absolute -right-2 -top-2 flex h-12 w-12 animate-pulse items-center justify-center rounded-pill bg-primary text-on-primary shadow-fab-mobile">
            <Icon name="auto_awesome" size={26} />
          </span>
        </div>
      }
      title={gettext('Sto componendo il piano…')}
      description={
        plan.error
          ? gettext('In pausa: Gemini è sovraccarico, riprovo da solo tra qualche minuto.')
          : interpolate(gettext('Settimana %s di %s. Puoi uscire: continuo io.'), [
              Math.min(plan.weeks_done + 1, plan.weeks_total),
              plan.weeks_total,
            ])
      }
      action={
        <div className="w-56">
          {plan.weeks_total > 1 ? (
            <Progress value={plan.weeks_done} max={plan.weeks_total} label={gettext('Settimane')} />
          ) : (
            <div className="progress-indeterminate" />
          )}
        </div>
      }
    />
  )
}

/* ----------------------------------------------------------- cosa mangi ---- */

function mealsByDay(plan: MealPlanDetail) {
  const out = new Map<string, PlannedMeal[]>()
  for (const meal of plan.meals) {
    out.set(meal.date, [...(out.get(meal.date) ?? []), meal])
  }
  for (const list of out.values()) {
    list.sort((a, b) => SLOT_ORDER.indexOf(a.slot) - SLOT_ORDER.indexOf(b.slot))
  }
  return out
}

function EatView({ plan, days, today }: { plan: MealPlanDetail; days: string[]; today: string }) {
  const byDay = useMemo(() => mealsByDay(plan), [plan])
  const [editing, setEditing] = useState<PlannedMeal | null>(null)
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {days.map((day) => (
        <section
          key={day}
          className={clsx(
            'rounded-card bg-surface-container-low p-4',
            day === today && 'ring-2 ring-primary',
          )}
        >
          <h2 className="mb-2 flex items-center gap-2 text-title-medium">
            {formatDayLong(day)}
            {day === today && (
              <span className="rounded-pill bg-primary px-2 py-0.5 text-label-small text-on-primary">
                {gettext('Oggi')}
              </span>
            )}
          </h2>
          <ul className="grid gap-2">
            {(byDay.get(day) ?? []).map((meal) => (
              <MealRow key={meal.id} meal={meal} onEdit={() => setEditing(meal)} />
            ))}
          </ul>
        </section>
      ))}
      {editing && <ChangeMealDialog plan={plan} meal={editing} onClose={() => setEditing(null)} />}
    </div>
  )
}

/** "pasta 80 g · zucchina ½ pz": le grammature, moltiplicate per ``factor``. */
export function Portion({
  lines,
  factor = 1,
  label,
}: {
  lines: PortionLine[]
  factor?: number
  label: string
}) {
  if (!lines.length) return null
  return (
    <p className="mt-1 text-body-small text-on-surface">
      <span className="font-medium text-primary">{label}</span>{' '}
      {lines.map((line, index) => (
        <Fragment key={`${line.name}-${index}`}>
          {index > 0 && <span className="text-on-surface-variant"> · </span>}
          {/* Si va a capo fra un alimento e l'altro, mai dentro "80 g". */}
          <span>
            {line.name}{' '}
            <span className="amount whitespace-nowrap font-medium">
              {formatQuantity(line.quantity, line.unit, factor)}
              {line.approx && (
                <span className="font-normal text-on-surface-variant">
                  {' '}
                  (~{formatQuantity(line.approx.quantity, line.approx.unit, factor)})
                </span>
              )}
            </span>
          </span>
        </Fragment>
      ))}
    </p>
  )
}

export function MealRow({ meal, onEdit }: { meal: PlannedMeal; onEdit?: () => void }) {
  const slot = MEAL_OPTIONS.find((option) => option.value === meal.slot)
  const recipe = meal.recipe
  const restrictions = recipe?.warnings.filter((item) => item.kind !== 'dislike') ?? []
  return (
    <li className="flex items-start gap-3 rounded-row bg-surface p-2">
      <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-[14px]">
        {recipe ? (
          <RecipeCover recipe={recipe} size={28} />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-surface-container-high">
            <Icon name={slot?.icon ?? 'restaurant'} size={22} className="text-on-surface-variant" />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-label-small text-on-surface-variant">{slot?.label}</p>
        {recipe ? (
          <Link
            to={`/ricette/${recipe.id}`}
            className="block truncate text-body-large font-medium hover:underline"
          >
            {recipe.title}
          </Link>
        ) : (
          <p className="text-body-medium italic text-on-surface-variant">
            {meal.note || gettext('Pasto libero')}
          </p>
        )}
        <p className="flex flex-wrap items-center gap-x-2 text-body-small text-on-surface-variant">
          {recipe && recipe.total_minutes > 0 && <span>{formatMinutes(recipe.total_minutes)}</span>}
          {meal.cooked_on !== meal.date && (
            <span className="inline-flex items-center gap-0.5 text-primary">
              <Icon name="kitchen" size={14} />
              {interpolate(gettext('cucinato %s'), [formatWeekday(meal.cooked_on)])}
            </span>
          )}
          {recipe && !recipe.in_cookbook && (
            <span className="inline-flex items-center gap-0.5">
              <Icon name={recipe.book ? 'library_books' : 'auto_awesome'} size={14} />
              {recipe.book ? gettext('dal PDF') : gettext('nuova')}
            </span>
          )}
          {restrictions.length > 0 && (
            <span className="inline-flex items-center gap-0.5 text-error">
              <Icon name="warning" size={14} filled />
              {gettext('da controllare')}
            </span>
          )}
        </p>
        <Portion lines={meal.portion ?? []} label={gettext('A porzione:')} />
      </div>
      {onEdit && (
        <IconButton icon="swap_horiz" label={gettext('Cambia il pasto')} onClick={onEdit} />
      )}
    </li>
  )
}

/* ---------------------------------------------------------- cosa cucini ---- */

function CookView({ plan, days, today }: { plan: MealPlanDetail; days: string[]; today: string }) {
  // Le sessioni: i pasti con una ricetta, raggruppati per giorno di cottura;
  // dentro, una riga per ricetta con le porzioni sommate.
  const sessions = useMemo(() => {
    const visible = new Set(days)
    const byDay = new Map<
      string,
      Map<string, { meal: PlannedMeal; servings: number; for: PlannedMeal[] }>
    >()
    for (const meal of plan.meals) {
      if (!meal.recipe || !visible.has(meal.date)) continue
      const day = byDay.get(meal.cooked_on) ?? new Map()
      const entry = day.get(meal.recipe.id) ?? { meal, servings: 0, for: [] }
      entry.servings += meal.servings
      entry.for.push(meal)
      day.set(meal.recipe.id, entry)
      byDay.set(meal.cooked_on, day)
    }
    return [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [plan, days])

  if (!sessions.length) {
    return <EmptyState icon="skillet" title={gettext('Niente da cucinare in questa settimana')} />
  }
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {sessions.map(([day, recipes]) => {
        const items = [...recipes.values()]
        const minutes = items.reduce(
          (total, item) => total + (item.meal.recipe?.total_minutes ?? 0),
          0,
        )
        return (
          <section
            key={day}
            className={clsx(
              'rounded-card bg-surface-container-low p-4',
              day === today && 'ring-2 ring-primary',
            )}
          >
            <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-title-medium">{formatDayLong(day)}</h2>
              <span className="text-body-small text-on-surface-variant">
                {interpolate(ngettext('%s ricetta', '%s ricette', items.length), [items.length])}
                {minutes > 0 && ` · ~${formatMinutes(minutes)}`}
              </span>
            </header>
            <ul className="grid gap-2">
              {items.map((item) => (
                <li
                  key={item.meal.recipe!.id}
                  className="flex items-center gap-3 rounded-row bg-surface p-2"
                >
                  <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-[14px]">
                    <RecipeCover recipe={item.meal.recipe!} size={28} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <Link
                      to={`/ricette/${item.meal.recipe!.id}`}
                      className="block truncate text-body-large font-medium hover:underline"
                    >
                      {item.meal.recipe!.title}
                    </Link>
                    <p className="text-body-small text-on-surface-variant">
                      {interpolate(ngettext('%s porzione', '%s porzioni', item.servings), [
                        item.servings,
                      ])}
                      {' · '}
                      {interpolate(gettext('per %s'), [
                        item.for
                          .map(
                            (meal) =>
                              `${formatDayShort(meal.date)} ${MEAL_OPTIONS.find((o) => o.value === meal.slot)?.label.toLowerCase()}`,
                          )
                          .join(', '),
                      ])}
                    </p>
                    <Portion
                      lines={item.meal.portion ?? []}
                      factor={item.servings}
                      label={gettext('Da cucinare:')}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

/* ---------------------------------------------------------- cambio pasto ---- */

type Source = 'cookbook' | 'books' | 'ai'

function ChangeMealDialog({
  plan,
  meal,
  onClose,
}: {
  plan: MealPlanDetail
  meal: PlannedMeal
  onClose: () => void
}) {
  const update = useUpdateMeal(plan.id)
  const [servings, setServings] = useState(meal.servings)
  const { data: cookbook } = useRecipes({})
  const { data: books } = useBooks()
  const readyBooks = (books ?? []).filter((book) => book.recipe_count > 0)
  const [source, setSource] = useState<Source | null>(null)
  // Con il ricettario vuoto si apre direttamente su "Inventa".
  const active: Source = source ?? (cookbook && cookbook.count === 0 ? 'ai' : 'cookbook')
  const slot = MEAL_OPTIONS.find((option) => option.value === meal.slot)

  const save = async (changes: { recipe_id?: string | null; servings?: number }) => {
    try {
      await update.mutateAsync({ id: meal.id, ...changes })
      onClose()
    } catch {
      // L'errore si vede nel dialog.
    }
  }

  const tabs: { value: Source; label: string; icon: string }[] = [
    { value: 'cookbook', label: gettext('Il mio ricettario'), icon: 'menu_book' },
    ...(readyBooks.length
      ? [{ value: 'books' as const, label: gettext('Ricettari PDF'), icon: 'library_books' }]
      : []),
    { value: 'ai', label: gettext('Inventa'), icon: 'auto_awesome' },
  ]

  return (
    <Modal open onClose={onClose} title={`${formatDayLong(meal.date)} · ${slot?.label ?? ''}`}>
      <div className="grid gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-body-large">{gettext('Porzioni')}</span>
          <Stepper
            label={gettext('Porzioni')}
            value={servings}
            min={1}
            max={50}
            onChange={setServings}
          />
        </div>
        {servings !== meal.servings && (
          <button type="button" className="btn-tonal w-fit" onClick={() => save({ servings })}>
            {gettext('Salva le porzioni')}
          </button>
        )}
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <Chip
              key={tab.value}
              icon={tab.icon}
              label={tab.label}
              selected={active === tab.value}
              onClick={() => setSource(tab.value)}
            />
          ))}
        </div>
        {active === 'cookbook' && (
          <RecipePicker
            meal={meal}
            onPick={(id) => save({ recipe_id: id })}
            empty={gettext(
              'Il tuo ricettario è vuoto: prova un ricettario PDF o fatti inventare una ricetta.',
            )}
            placeholder={gettext('Cerca nel tuo ricettario')}
          />
        )}
        {active === 'books' && (
          <BookPicker meal={meal} books={readyBooks} onPick={(id) => save({ recipe_id: id })} />
        )}
        {active === 'ai' && (
          <MealIdeas plan={plan} meal={meal} onPick={(id) => save({ recipe_id: id })} />
        )}
        <ErrorBanner error={update.error} />
        <div className="flex justify-between gap-2">
          <button
            type="button"
            className="btn-text text-error"
            onClick={() => save({ recipe_id: null })}
          >
            <Icon name="do_not_disturb_on" size={20} />
            {gettext('Pasto libero')}
          </button>
          <button type="button" className="btn-text" onClick={onClose}>
            {gettext('Chiudi')}
          </button>
        </div>
      </div>
    </Modal>
  )
}

/** Ricerca nel ricettario o in un ricettario PDF (``book``) e scelta. */
function RecipePicker({
  meal,
  book,
  onPick,
  empty,
  placeholder,
}: {
  meal: PlannedMeal
  book?: string
  onPick: (id: string) => void
  empty: string
  placeholder: string
}) {
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(text.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [text])
  const { data: recipes, isPending } = useRecipes({ q: query, book })
  return (
    <div className="grid gap-2">
      <label className="flex items-center gap-3 rounded-pill bg-surface-container-high px-5 py-3">
        <Icon name="search" size={22} className="text-on-surface-variant" />
        <input
          className="min-w-0 flex-1 bg-transparent text-body-large outline-none"
          placeholder={placeholder}
          value={text}
          onChange={(event) => setText(event.target.value)}
          type="search"
        />
      </label>
      {!isPending && !recipes?.results.length && (
        <p className="px-1 text-body-medium text-on-surface-variant">
          {query ? gettext('Nessuna ricetta trovata.') : empty}
        </p>
      )}
      <ul className="grid max-h-72 gap-1 overflow-y-auto">
        {recipes?.results.map((recipe) => (
          <li key={recipe.id}>
            <PickRow recipe={recipe} current={recipe.id === meal.recipe?.id} onPick={onPick} />
          </li>
        ))}
      </ul>
    </div>
  )
}

function BookPicker({
  meal,
  books,
  onPick,
}: {
  meal: PlannedMeal
  books: RecipeBook[]
  onPick: (id: string) => void
}) {
  const [bookId, setBookId] = useState(books[0]?.id)
  return (
    <div className="grid gap-2">
      {books.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {books.map((book) => (
            <Chip
              key={book.id}
              label={book.title}
              selected={book.id === bookId}
              onClick={() => setBookId(book.id)}
            />
          ))}
        </div>
      )}
      {bookId && (
        <RecipePicker
          key={bookId}
          meal={meal}
          book={bookId}
          onPick={onPick}
          empty={gettext('Questo ricettario non ha ricette.')}
          placeholder={gettext('Cerca nel ricettario PDF')}
        />
      )}
    </div>
  )
}

function PickRow({
  recipe,
  current,
  onPick,
}: {
  recipe: RecipeSummary
  current: boolean
  onPick: (id: string) => void
}) {
  return (
    <button
      type="button"
      className={clsx(
        'state flex w-full items-center gap-3 rounded-row px-3 py-2 text-left',
        current && 'bg-primary-container',
      )}
      onClick={() => onPick(recipe.id)}
    >
      <span className="relative h-9 w-9 shrink-0 overflow-hidden rounded-[10px]">
        <RecipeCover recipe={recipe} size={20} />
      </span>
      <span className="min-w-0 flex-1 truncate text-body-large">{recipe.title}</span>
      {recipe.warnings.some((item) => item.kind !== 'dislike') && (
        <span title={gettext('Tocca un’allergia o un’intolleranza del profilo')}>
          <Icon name="warning" size={18} filled className="text-error" />
        </span>
      )}
      {recipe.total_minutes > 0 && (
        <span className="text-body-small text-on-surface-variant">
          {formatMinutes(recipe.total_minutes)}
        </span>
      )}
    </button>
  )
}

/** "Inventa": due ricette nuove per questo pasto, scritte dall'AI in un job. */
function MealIdeas({
  plan,
  meal,
  onPick,
}: {
  plan: MealPlanDetail
  meal: PlannedMeal
  onPick: (id: string) => void
}) {
  const ask = useMealIdeas(plan.id)
  const [hint, setHint] = useState('')
  const [jobId, setJobId] = useState<string>()
  const { data: job } = useJob(jobId)
  const working = ask.isPending || job?.status === 'queued' || job?.status === 'running'
  const ideas = job?.status === 'ready' ? (job.result.ideas ?? []) : []
  return (
    <div className="grid gap-3">
      <Field
        label={gettext('Hai un desiderio? (facoltativo)')}
        hint={gettext('Es. “qualcosa col pesce”, “leggero”, “da portare in ufficio”.')}
      >
        <input
          className="field-input"
          maxLength={200}
          value={hint}
          onChange={(event) => setHint(event.target.value)}
        />
      </Field>
      <button
        type="button"
        className="btn-filled w-fit"
        disabled={working}
        onClick={async () => {
          try {
            const started = await ask.mutateAsync({ mealId: meal.id, hint })
            setJobId(started.id)
          } catch {
            // Errore sotto.
          }
        }}
      >
        <Icon name="auto_awesome" size={20} />
        {ideas.length ? gettext('Altre idee') : gettext('Proponimi due ricette')}
      </button>
      {working && (
        <p className="flex items-center gap-2 text-body-medium text-on-surface-variant">
          <Icon name="hourglass_top" size={20} className="animate-pulse" />
          {gettext('Scrivo due ricette adatte a questo pasto…')}
        </p>
      )}
      {job?.status === 'ready' && !ideas.length && (
        <p className="text-body-medium text-on-surface-variant">
          {gettext('Questa volta niente di adatto: riprova, magari con un desiderio.')}
        </p>
      )}
      {ideas.length > 0 && (
        <ul className="grid gap-1">
          {ideas.map((recipe) => (
            <li key={recipe.id}>
              <PickRow recipe={recipe} current={false} onPick={onPick} />
            </li>
          ))}
        </ul>
      )}
      <ErrorBanner error={ask.error ?? (job?.status === 'failed' ? job.error : null)} />
    </div>
  )
}
