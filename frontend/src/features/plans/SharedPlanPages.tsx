// Piano fatto vedere a un altro account, in sola lettura (ADR 0019): chi
// condivide sceglie con chi dall'email; chi riceve guarda il piano di oggi
// dell'altro e le sue ricette, e il suo piano se lo crea da sé.

import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  useDeletePlanShare,
  usePlanShares,
  useSharePlan,
  useSharedPlan,
  useSharedPlanRecipe,
} from '../../api/hooks'
import { useConfirm } from '../../components/ConfirmDialog'
import { Page } from '../../components/Layout'
import { FoodPattern, RecipeCover } from '../../components/illustrations'
import {
  Avatar,
  Chip,
  EmptyState,
  ErrorBanner,
  Field,
  Icon,
  IconButton,
  Modal,
  Segmented,
  Skeleton,
  Stepper,
} from '../../components/ui'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { MealPlanDetail } from '../../lib/types'
import { formatQuantity } from '../recipes/options'
import { addDays, formatRange, todayIso } from './dates'
import { CookView, EatView, RecipeLinkContext } from './PlanPages'

/* ------------------------------------------- dialogo "fallo vedere" ---- */

export function SharePlanDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: shares } = usePlanShares()
  const share = useSharePlan()
  const remove = useDeletePlanShare()
  const confirm = useConfirm()
  const [email, setEmail] = useState('')

  return (
    <Modal open={open} onClose={onClose} title={gettext('Fai vedere il tuo piano')}>
      <div className="grid gap-4">
        <p className="text-body-medium text-on-surface-variant">
          {gettext(
            'Chi scegli vede il tuo piano di oggi e le sue ricette, sempre aggiornato, ma non può cambiarlo. Gli arriva una mail. Serve che abbia un account.',
          )}
        </p>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={async (event) => {
            event.preventDefault()
            try {
              await share.mutateAsync(email.trim())
              setEmail('')
            } catch {
              // Errore sotto.
            }
          }}
        >
          <Field label={gettext('Email')} className="min-w-[220px] flex-1">
            <input
              className="field-input"
              type="email"
              autoComplete="off"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </Field>
          <button className="btn-filled" disabled={share.isPending || !email.trim()}>
            <Icon name="group_add" size={20} />
            {gettext('Condividi')}
          </button>
        </form>
        <ErrorBanner error={share.error ?? remove.error} />
        {shares && shares.given.length > 0 && (
          <section>
            <h3 className="mb-1 text-body-medium font-medium text-on-surface-variant">
              {gettext('Lo vedono')}
            </h3>
            <ul className="divide-y divide-outline-variant">
              {shares.given.map((person) => (
                <li key={person.share} className="flex items-center gap-3 py-2">
                  <Avatar name={person.name} size={32} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-body-large">{person.name}</span>
                    <span className="block truncate text-body-small text-on-surface-variant">
                      {person.email}
                    </span>
                  </span>
                  <IconButton
                    icon="person_remove"
                    label={gettext('Non farlo più vedere')}
                    onClick={async () => {
                      const ok = await confirm({
                        title: interpolate(gettext('Non far più vedere il piano a %s?'), [
                          person.name,
                        ]),
                        message: gettext('Puoi condividerlo di nuovo quando vuoi.'),
                        confirmLabel: gettext('Togli'),
                        icon: 'person_remove',
                        destructive: true,
                      })
                      if (ok) remove.mutate(person.share)
                    }}
                  />
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </Modal>
  )
}

/* ------------------------------------ i piani che vedo, sotto il mio ---- */

export function SharedWithMe() {
  const { data: shares } = usePlanShares()
  if (!shares?.received.length) return null
  return (
    <section className="mt-4 grid gap-2">
      <h2 className="text-title-medium">{gettext('Piani che ti fanno vedere')}</h2>
      {shares.received.map((person) => (
        <Link
          key={person.share}
          to={`/piano/condivisi/${person.share}`}
          className="state flex items-center gap-4 rounded-card bg-surface-container-low p-4"
        >
          <Avatar name={person.name} size={44} />
          <span className="min-w-0 flex-1">
            <span className="block text-body-large font-medium">
              {interpolate(gettext('Il piano di %s'), [person.name])}
            </span>
            <span className="block text-body-small text-on-surface-variant">
              {person.has_plan
                ? gettext('Solo da guardare: il tuo resta tuo')
                : gettext('Per ora non ha un piano attivo')}
            </span>
          </span>
          <Icon name="chevron_right" size={22} />
        </Link>
      ))}
    </section>
  )
}

/* ------------------------------------------ /piano/condivisi/:shareId ---- */

export function SharedPlanPage() {
  const { shareId } = useParams()
  const { data, error, isPending } = useSharedPlan(shareId)
  const remove = useDeletePlanShare()
  const confirm = useConfirm()

  if (isPending) return <Skeleton className="m-5 h-72 rounded-card md:m-8" />
  if (error || !data) {
    return (
      <Page className="px-5 pt-5 md:px-8 md:pt-8">
        <EmptyState
          icon="visibility_off"
          title={gettext('Questo piano non è più condiviso con te')}
          action={
            <Link to="/piano" className="btn-tonal">
              {gettext('Torna al tuo piano')}
            </Link>
          }
        />
      </Page>
    )
  }

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <Link to="/piano" className="btn-text btn-sm -ml-3 mb-2 w-fit">
        <Icon name="arrow_back" size={20} />
        {gettext('Il tuo piano')}
      </Link>
      {data.plan ? (
        <RecipeLinkContext.Provider value={(id) => `/piano/condivisi/${shareId}/ricette/${id}`}>
          <ReadOnlyPlan plan={data.plan} owner={data.owner.name} />
        </RecipeLinkContext.Provider>
      ) : (
        <EmptyState
          icon="event_busy"
          title={interpolate(gettext('%s non ha un piano attivo'), [data.owner.name])}
          description={gettext('Quando ne attiva uno lo vedi qui.')}
        />
      )}
      <button
        type="button"
        className="btn-text btn-sm mt-6"
        onClick={async () => {
          const ok = await confirm({
            title: gettext('Togliere questo piano dal tuo elenco?'),
            message: interpolate(gettext('Per rivederlo %s dovrà condividerlo di nuovo.'), [
              data.owner.name,
            ]),
            confirmLabel: gettext('Togli'),
            icon: 'visibility_off',
            destructive: true,
          })
          if (!ok) return
          await remove.mutateAsync(shareId!)
          window.location.replace('/piano')
        }}
      >
        <Icon name="visibility_off" size={18} />
        {gettext('Non mostrarmelo più')}
      </button>
      <ErrorBanner error={remove.error} />
    </Page>
  )
}

function ReadOnlyPlan({ plan, owner }: { plan: MealPlanDetail; owner: string }) {
  const [view, setView] = useState<'eat' | 'cook'>('eat')
  const today = todayIso()
  const days = useMemo(
    () => Array.from({ length: plan.days }, (_, offset) => addDays(plan.start_date, offset)),
    [plan.start_date, plan.days],
  )
  const [week, setWeek] = useState(() => {
    const index = days.indexOf(today)
    return index >= 0 ? Math.floor(index / 7) : 0
  })
  const weekDays = days.slice(week * 7, week * 7 + 7)

  return (
    <>
      <header className="relative mb-4 overflow-hidden rounded-panel bg-secondary-container px-5 py-5 text-on-secondary-container md:px-7">
        <FoodPattern opacity={0.25} />
        <div className="relative">
          <p className="flex items-center gap-1.5 text-body-medium">
            <Icon name="visibility" size={18} />
            {interpolate(gettext('Il piano di %s · solo da guardare'), [owner])}
          </p>
          <h1 className="text-[26px] font-medium leading-8">
            {formatRange(plan.start_date, plan.end_date)}
          </h1>
          {plan.settings.servings && (
            <p className="mt-1 text-body-small">
              {interpolate(ngettext('%s porzione', '%s porzioni', plan.settings.servings), [
                plan.settings.servings,
              ])}
            </p>
          )}
        </div>
      </header>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Segmented
          value={view}
          onChange={setView}
          options={[
            { value: 'eat', label: gettext('Cosa mangia') },
            { value: 'cook', label: gettext('Cosa cucina') },
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
        <EatView plan={plan} days={weekDays} today={today} editable={false} />
      ) : (
        <CookView plan={plan} days={weekDays} today={today} />
      )}
    </>
  )
}

/* ------------------------- /piano/condivisi/:shareId/ricette/:recipeId ---- */

export function SharedPlanRecipePage() {
  const { shareId, recipeId } = useParams()
  const { data: recipe, error, isPending } = useSharedPlanRecipe(shareId, recipeId)
  const [servings, setServings] = useState<number>()
  const back = `/piano/condivisi/${shareId}`

  if (isPending) return <Skeleton className="m-5 h-72 rounded-card md:m-8" />
  if (error || !recipe) {
    return (
      <Page className="px-5 pt-5 md:px-8 md:pt-8">
        <EmptyState
          icon="no_meals"
          title={gettext('Questa ricetta non è più nel piano')}
          action={
            <Link to={back} className="btn-tonal">
              {gettext('Torna al piano')}
            </Link>
          }
        />
      </Page>
    )
  }
  const shown = servings ?? recipe.servings
  const factor = shown / recipe.servings

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <Link to={back} className="btn-text btn-sm -ml-3 mb-2 w-fit">
        <Icon name="arrow_back" size={20} />
        {interpolate(gettext('Il piano di %s'), [recipe.author])}
      </Link>
      <div className="relative mb-4 h-48 overflow-hidden rounded-panel md:h-64">
        <RecipeCover recipe={recipe} size={80} />
      </div>
      <h1 className="text-[28px] font-medium leading-9 md:text-headline-small">{recipe.title}</h1>
      {recipe.description && (
        <p className="mt-2 whitespace-pre-line text-body-large text-on-surface-variant">
          {recipe.description}
        </p>
      )}
      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <section className="rounded-card bg-surface-container-low p-5">
          <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-title-medium">{gettext('Ingredienti')}</h2>
            <Stepper
              label={gettext('Porzioni')}
              value={shown}
              min={1}
              max={50}
              onChange={setServings}
              format={(value) =>
                interpolate(ngettext('%s porzione', '%s porzioni', value), [value])
              }
            />
          </header>
          <ul className="divide-y divide-outline-variant">
            {recipe.ingredients.map((line) => (
              <li key={line.id} className="flex items-baseline gap-3 py-2.5">
                <span className="min-w-0 flex-1 text-body-large">
                  {line.ingredient.name}
                  {line.note && <span className="text-on-surface-variant">, {line.note}</span>}
                </span>
                <span className="amount shrink-0 text-body-medium text-on-surface-variant">
                  {formatQuantity(line.quantity, line.unit, factor)}
                </span>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-card bg-surface-container-low p-5">
          <h2 className="mb-3 text-title-medium">{gettext('Preparazione')}</h2>
          <ol className="grid gap-3">
            {recipe.steps.map((step, index) => (
              <li key={index} className="flex gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-pill bg-primary text-label-large text-on-primary">
                  {index + 1}
                </span>
                <p className="whitespace-pre-line text-body-large">{step}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </Page>
  )
}
