import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import {
  useBooks,
  useCreatePlan,
  useNutritionistPlans,
  useProfile,
  useRecipes,
  useTags,
} from '../../api/hooks'
import { AiKeyIcon, useAiGate } from '../../components/Ai'
import { AiCost } from '../../components/AiCost'
import { Page } from '../../components/Layout'
import { FoodPattern } from '../../components/illustrations'
import {
  Chip,
  ChipEditor,
  ErrorBanner,
  Field,
  Icon,
  IconButton,
  Segmented,
  Skeleton,
  Stepper,
} from '../../components/ui'
import { ApiError } from '../../lib/api'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { NutritionistPlan, PlanPayload, Profile } from '../../lib/types'
import { MEAL_OPTIONS } from '../profile/options'
import { DIFFICULTY_OPTIONS } from '../recipes/options'
import { GuidelinesButton } from './NutritionistPages'
import { formatDayLong, nextMondayIso, todayIso } from './dates'
import { MINUTES_OPTIONS, PREP_OPTIONS } from './options'

/**
 * "Nuova preparazione": le scelte con cui l'LLM mette il piano alimentare nei
 * giorni, per ingredienti, e sceglie le ricette da suggerire (ADR 0023).
 */
export function NewPlanPage() {
  const { data: profile } = useProfile()
  if (!profile) return <Skeleton className="m-5 h-72 rounded-card md:m-8" />
  return <NewPlanForm profile={profile} />
}

function NewPlanForm({ profile }: { profile: Profile }) {
  const navigate = useNavigate()
  const create = useCreatePlan()
  const { data: books } = useBooks()
  const { data: tags } = useTags()
  const { data: cookbook } = useRecipes({})
  const { data: nutritionistPlans } = useNutritionistPlans()
  const [params] = useSearchParams()
  const confirmed = (nutritionistPlans ?? []).filter((item) => item.status === 'confirmed')
  const [plan, setPlan] = useState<PlanPayload>(() => ({
    start_date: nextMondayIso(),
    days: 7,
    slots: profile.meal_slots.length ? profile.meal_slots : ['lunch', 'dinner'],
    servings: profile.household_size || 1,
    prep_mode: 'evening_before',
    minutes: 45,
    difficulty: 'medium',
    use_cookbook: true,
    books: [],
    include_tags: [],
    exclude_tags: [],
    goal_note: '',
    nutritionist_plan: '',
  }))
  const set = (changes: Partial<PlanPayload>) => setPlan((current) => ({ ...current, ...changes }))
  // Seguire il piano alimentare non tocca i pasti scelti: le sue regole
  // valgono per quelli che ci sono. Prima li sostituiva con tutti i suoi, in
  // silenzio, e colazione e merende tornavano anche se l'utente le aveva tolte.
  const follow = (chosen: NutritionistPlan) => set({ nutritionist_plan: chosen.id })
  // Arrivati da "Prepara le settimane": quel piano gia' scelto; se no il piu' recente.
  const preset = useRef(params.get('nutrizionista'))
  useEffect(() => {
    if (!confirmed.length || (plan.nutritionist_plan && !preset.current)) return
    const chosen = confirmed.find((item) => item.id === preset.current) ?? confirmed[0]
    preset.current = null
    follow(chosen)
  })
  const gate = useAiGate('plan_week', { count: Math.ceil(plan.days / 7) })
  const errors = create.error instanceof ApiError ? create.error.fieldErrors() : {}
  const readyBooks = (books ?? []).filter((book) => book.recipe_count > 0)
  const recipeCount = cookbook?.count ?? 0
  const noSource = !plan.use_cookbook && !plan.books.length
  const today = todayIso()
  const monday = nextMondayIso()

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="mb-5 flex items-center gap-3">
        <IconButton
          icon="close"
          size="md"
          label={gettext('Annulla')}
          onClick={() => navigate('/piano')}
        />
        <h1 className="flex-1 text-title-large">{gettext('Nuova preparazione')}</h1>
      </header>

      <div className="grid gap-4">
        <section className="relative overflow-hidden rounded-panel bg-primary px-6 py-6 text-on-primary">
          <FoodPattern tone="dark" opacity={0.3} />
          <p className="relative max-w-xl text-body-large">
            {gettext(
              'Metto il tuo piano alimentare nei giorni: per ogni pasto ingredienti e quantità a persona, con il meal prep che preferisci. Sotto ti suggerisco le ricette per cucinarli.',
            )}
          </p>
        </section>

        <Card title={gettext('Quando e per quanto')} icon="date_range">
          <div className="flex flex-wrap gap-2">
            <Chip
              label={interpolate(gettext('Da lunedì %s'), [
                formatDayLong(monday).split(' ').slice(1).join(' '),
              ])}
              selected={plan.start_date === monday}
              onClick={() => set({ start_date: monday })}
            />
            {today !== monday && (
              <Chip
                label={gettext('Da oggi')}
                selected={plan.start_date === today}
                onClick={() => set({ start_date: today })}
              />
            )}
          </div>
          <Field label={gettext('Primo giorno')} error={errors.start_date}>
            <input
              className="field-input"
              type="date"
              min={today}
              value={plan.start_date}
              onChange={(event) => event.target.value && set({ start_date: event.target.value })}
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            {([7, 14, 21, 28] as const).map((days) => (
              <Chip
                key={days}
                label={interpolate(ngettext('%s settimana', '%s settimane', days / 7), [days / 7])}
                selected={plan.days === days}
                onClick={() => set({ days })}
              />
            ))}
          </div>
        </Card>

        <Card title={gettext('Il piano da seguire')} icon="nutrition">
          {confirmed.length ? (
            <>
              {confirmed.map((item) => (
                <SourceToggle
                  key={item.id}
                  icon={item.source === 'guidelines' ? 'nutrition' : 'clinical_notes'}
                  label={item.title}
                  hint={[
                    item.source === 'guidelines'
                      ? gettext('Dalle linee guida')
                      : gettext('Dal nutrizionista'),
                    item.strict
                      ? gettext('alla lettera')
                      : gettext('con alimenti equivalenti'),
                  ].join(' · ')}
                  checked={plan.nutritionist_plan === item.id}
                  onChange={() => follow(item)}
                />
              ))}
              <p className="text-body-small text-on-surface-variant">
                {gettext(
                  'Ogni pasto segue le sue opzioni e grammature; frequenze e alimenti da evitare li controllo io.',
                )}
              </p>
            </>
          ) : (
            <>
              <p className="text-body-medium text-on-surface-variant">
                {gettext(
                  'Prima serve il piano alimentare: cosa dovresti mangiare, con quantità e frequenze. Lo scrivo io dalle linee guida o lo carichi dal tuo nutrizionista; poi torni qui.',
                )}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <GuidelinesButton />
                <Link to="/piano/nutrizionista" className="btn-outlined">
                  <Icon name="clinical_notes" size={20} />
                  {gettext('Dal nutrizionista')}
                </Link>
              </div>
            </>
          )}
          {errors.nutritionist_plan && (
            <p className="text-body-small text-error">{errors.nutritionist_plan}</p>
          )}
        </Card>

        <Card title={gettext('Pasti e porzioni')} icon="restaurant">
          <div className="flex flex-wrap gap-2">
            {MEAL_OPTIONS.map((option) => {
              const active = plan.slots.includes(option.value)
              return (
                <Chip
                  key={option.value}
                  icon={active ? 'check' : option.icon}
                  label={option.label}
                  selected={active}
                  onClick={() =>
                    set({
                      slots: active
                        ? plan.slots.filter((slot) => slot !== option.value)
                        : [...plan.slots, option.value],
                    })
                  }
                />
              )
            })}
          </div>
          {errors.slots && <p className="text-body-small text-error">{errors.slots}</p>}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-body-large">{gettext('Porzioni per pasto')}</span>
            <Stepper
              label={gettext('Porzioni per pasto')}
              value={plan.servings}
              min={1}
              max={12}
              onChange={(servings) => set({ servings })}
            />
          </div>
        </Card>

        <Card title={gettext('Meal prep')} icon="kitchen">
          <div className="grid gap-2">
            {PREP_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={plan.prep_mode === option.value}
                onClick={() => set({ prep_mode: option.value })}
                className={clsx(
                  'state flex items-center gap-3 rounded-row px-4 py-3 text-left transition',
                  plan.prep_mode === option.value
                    ? 'bg-primary-container text-on-primary-container'
                    : 'bg-surface-container text-on-surface',
                )}
              >
                <Icon name={option.icon} size={24} filled={plan.prep_mode === option.value} />
                <span className="min-w-0 flex-1">
                  <span className="block text-body-large font-medium">{option.label}</span>
                  <span className="block text-body-small opacity-80">{option.hint}</span>
                </span>
                <Icon
                  name="check_circle"
                  size={22}
                  filled
                  className={clsx('shrink-0', plan.prep_mode !== option.value && 'invisible')}
                />
              </button>
            ))}
          </div>
          <div>
            <p className="mb-2 text-body-large">{gettext('Tempo per cucinare, ogni volta')}</p>
            <div className="flex flex-wrap gap-2">
              {MINUTES_OPTIONS.map((minutes) => (
                <Chip
                  key={minutes}
                  label={minutes < 60 ? `${minutes} min` : `${minutes / 60} h`}
                  selected={plan.minutes === minutes}
                  onClick={() => set({ minutes })}
                />
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-body-large">{gettext('Difficoltà massima')}</span>
            <Segmented
              value={plan.difficulty}
              options={DIFFICULTY_OPTIONS}
              onChange={(difficulty) => set({ difficulty })}
            />
          </div>
        </Card>

        <Card title={gettext('Da dove prendo le ricette da suggerire')} icon="menu_book">
          <SourceToggle
            icon="menu_book"
            label={gettext('Il mio ricettario')}
            hint={interpolate(ngettext('%s ricetta', '%s ricette', recipeCount), [recipeCount])}
            checked={plan.use_cookbook}
            onChange={(use_cookbook) => set({ use_cookbook })}
          />
          {readyBooks.map((book) => (
            <SourceToggle
              key={book.id}
              icon="library_books"
              label={book.title}
              hint={interpolate(ngettext('%s ricetta', '%s ricette', book.recipe_count), [
                book.recipe_count,
              ])}
              checked={plan.books.includes(book.id)}
              onChange={(checked) =>
                set({
                  books: checked
                    ? [...plan.books, book.id]
                    : plan.books.filter((id) => id !== book.id),
                })
              }
            />
          ))}
          <p className="text-body-small text-on-surface-variant">
            {gettext(
              'Sotto ogni pasto ti suggerisco le ricette che usano quegli ingredienti; se non ce ne sono, un’idea che scrivo per intero quando la apri.',
            )}
          </p>
          {(errors.books || noSource) && (
            <p className="text-body-small text-error">
              {errors.books || gettext('Scegli almeno una fonte.')}
            </p>
          )}
        </Card>

        <Card title={gettext('Tag')} icon="sell">
          <div>
            <p className="mb-2 text-body-large">{gettext('Solo ricette con questi tag')}</p>
            <ChipEditor
              inputLabel={gettext('Tag da includere (vuoto = tutte)')}
              items={plan.include_tags.map((tag) => ({ key: tag, label: tag }))}
              suggestions={(tags ?? []).map((tag) => tag.name)}
              onAdd={(tag) => set({ include_tags: [...plan.include_tags, tag] })}
              onRemove={(tag) => set({ include_tags: plan.include_tags.filter((t) => t !== tag) })}
            />
          </div>
          <div>
            <p className="mb-2 text-body-large">{gettext('Mai ricette con questi tag')}</p>
            <ChipEditor
              inputLabel={gettext('Tag da escludere (es. “del cuore”)')}
              items={plan.exclude_tags.map((tag) => ({ key: tag, label: tag }))}
              suggestions={(tags ?? []).map((tag) => tag.name)}
              onAdd={(tag) => set({ exclude_tags: [...plan.exclude_tags, tag] })}
              onRemove={(tag) => set({ exclude_tags: plan.exclude_tags.filter((t) => t !== tag) })}
            />
          </div>
        </Card>

        <Card
          title={gettext('Qualcosa da aggiungere?')}
          icon="flag"
        >
          <Field
            label={gettext('In parole tue')}
            hint={gettext('Es. “più proteine e pranzi leggeri da portare in ufficio”.')}
          >
            <textarea
              className="field-input min-h-[72px] resize-y"
              maxLength={500}
              value={plan.goal_note}
              onChange={(event) => set({ goal_note: event.target.value })}
            />
          </Field>
        </Card>

        <ErrorBanner error={create.error} />
        <div className="flex flex-wrap items-center justify-end gap-2">
          {/* Una chiamata per settimana (due se le frequenze vanno corrette). */}
          <AiCost feature="plan_week" count={Math.ceil(plan.days / 7)} />
          <button type="button" className="btn-text" onClick={() => navigate('/piano')}>
            {gettext('Annulla')}
          </button>
          <button
            type="button"
            className="btn-filled"
            disabled={
              !gate.allowed ||
              create.isPending ||
              !plan.slots.length ||
              noSource ||
              !plan.nutritionist_plan
            }
            onClick={async () => {
              try {
                const created = await create.mutateAsync(plan)
                navigate(`/piano/${created.id}`, { replace: true })
              } catch {
                // Errori sui campi e in fondo.
              }
            }}
          >
            <Icon name="auto_awesome" size={20} />
            {gettext('Prepara le settimane')}
            {gate.large && <AiKeyIcon />}
          </button>
        </div>
      </div>
    </Page>
  )
}

function Card({
  title,
  icon,
  children,
}: {
  title: string
  icon: string
  children: React.ReactNode
}) {
  return (
    <section className="grid gap-4 rounded-card bg-surface-container-low p-5">
      <h2 className="flex items-center gap-2 text-title-medium">
        <Icon name={icon} size={22} className="text-primary" />
        {title}
      </h2>
      {children}
    </section>
  )
}

function SourceToggle({
  icon,
  label,
  hint,
  checked,
  onChange,
}: {
  icon: string
  label: string
  hint: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <button
      type="button"
      aria-pressed={checked}
      onClick={() => onChange(!checked)}
      className={clsx(
        'state flex items-center gap-3 rounded-row px-4 py-3 text-left transition',
        checked ? 'bg-primary-container text-on-primary-container' : 'bg-surface-container',
      )}
    >
      <Icon name={icon} size={22} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-body-large font-medium">{label}</span>
        <span className="block text-body-small opacity-80">{hint}</span>
      </span>
      <Icon name={checked ? 'check_box' : 'check_box_outline_blank'} size={22} filled={checked} />
    </button>
  )
}
