// Cosa cucino oggi? (ADR 0009): cosa c'e' in casa (scritto o fotografato),
// le ricette che si possono fare gia' adesso e due idee nuove.

import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { useCookSuggestions, useJob, useProfile, useScanFridge } from '../../api/hooks'
import { Page } from '../../components/Layout'
import { FoodPattern, RecipeCover } from '../../components/illustrations'
import {
  Chip,
  ChipEditor,
  EmptyState,
  ErrorBanner,
  Icon,
  Skeleton,
  Stepper,
  Switch,
} from '../../components/ui'
import { gettext, interpolate } from '../../lib/i18n'
import type { CookMatch, CookSuggestions, MealSlot, RecipeSummary } from '../../lib/types'
import { MEAL_OPTIONS } from '../profile/options'
import { difficultyLabel, formatMinutes } from '../recipes/options'

const COMMON = [
  gettext('uova'),
  gettext('pasta'),
  gettext('riso'),
  gettext('zucchine'),
  gettext('pomodori'),
  gettext('cipolla'),
  gettext('patate'),
  gettext('mozzarella'),
  gettext('petto di pollo'),
  gettext('tonno in scatola'),
  gettext('ceci in scatola'),
  gettext('spinaci'),
]
const MINUTES = [15, 30, 45, 60]
const BACK = { from: '/cosa-cucino' }

/**
 * Stato della pagina in sessionStorage: aprendo una ricetta e tornando
 * indietro si ritrovano ingredienti e risultati, senza rifare la ricerca.
 */
function useSessionState<T>(key: string, initial: T | (() => T)) {
  const storageKey = `cook-today:${key}`
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = sessionStorage.getItem(storageKey)
      if (saved !== null) return JSON.parse(saved) as T
    } catch {
      // Storage non disponibile o valore rovinato: si riparte dal default.
    }
    return typeof initial === 'function' ? (initial as () => T)() : initial
  })
  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(value))
    } catch {
      // Niente storage: la pagina funziona lo stesso, solo senza memoria.
    }
  }, [storageKey, value])
  return [value, setValue] as const
}

/**
 * Radice grezza di un nome ("uova" e "uovo" -> "uov"): basta a non riproporre
 * come spunto un alimento gia' in lista al singolare o al plurale.
 */
function stem(name: string): string {
  return name
    .toLowerCase()
    .split(/\s+/)
    .map((word) => word.replace(/[aeiouàèéìòù]+$/, ''))
    .join(' ')
}

/** Il pasto piu' probabile adesso, dall'ora del giorno. */
function slotNow(): MealSlot {
  const hour = new Date().getHours()
  if (hour < 10) return 'breakfast'
  if (hour < 15) return 'lunch'
  if (hour < 18) return 'afternoon_snack'
  return 'dinner'
}

export function CookTodayPage() {
  const { data: profile } = useProfile()
  const suggest = useCookSuggestions()
  const [ingredients, setIngredients] = useSessionState<string[]>('ingredients', [])
  const [slot, setSlot] = useSessionState<MealSlot>('slot', slotNow)
  const [minutes, setMinutes] = useSessionState<number | null>('minutes', 30)
  const [servings, setServings] = useSessionState<number | null>('servings', null)
  const [books, setBooks] = useSessionState('books', true)
  const [result, setResult] = useSessionState<CookSuggestions | null>('result', null)
  const results = useRef<HTMLDivElement>(null)
  const people = servings ?? profile?.household_size ?? 2
  const stems = new Set(ingredients.map(stem))

  const add = (names: string[]) =>
    setIngredients((current) => {
      const seen = new Set(current.map((name) => name.toLowerCase()))
      return [...current, ...names.filter((name) => !seen.has(name.toLowerCase()))]
    })

  const run = async () => {
    try {
      const found = await suggest.mutateAsync({
        ingredients,
        slot,
        minutes,
        servings: people,
        include_books: books,
      })
      setResult(found)
      window.setTimeout(() => results.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    } catch {
      // Errore sotto il bottone.
    }
  }

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="relative mb-4 overflow-hidden rounded-panel bg-primary px-6 py-6 text-on-primary">
        <FoodPattern tone="dark" opacity={0.3} />
        <div className="relative">
          <h1 className="text-[28px] font-medium leading-9">{gettext('Cosa cucino oggi?')}</h1>
          <p className="mt-1 max-w-xl text-body-large opacity-90">
            {gettext(
              'Dimmi cosa c’è in casa, o fotografa il frigo: ti dico cosa puoi fare con le tue ricette e ti propongo qualcosa di nuovo.',
            )}
          </p>
        </div>
      </header>

      <div className="grid gap-4">
        <section className="grid gap-4 rounded-card bg-surface-container-low p-5">
          <h2 className="flex items-center gap-2 text-title-medium">
            <Icon name="kitchen" size={22} className="text-primary" />
            {gettext('Cosa c’è in casa?')}
          </h2>
          <FridgePhoto onFound={add} />
          <ChipEditor
            inputLabel={gettext('Aggiungi un ingrediente')}
            items={ingredients.map((name) => ({ key: name, label: name }))}
            suggestions={COMMON.filter((name) => !stems.has(stem(name)))}
            onAdd={(name) => add([name])}
            onRemove={(name) => setIngredients(ingredients.filter((other) => other !== name))}
          />
        </section>

        <section className="grid gap-4 rounded-card bg-surface-container-low p-5">
          <div className="flex flex-wrap gap-2">
            {MEAL_OPTIONS.map((option) => (
              <Chip
                key={option.value}
                icon={slot === option.value ? 'check' : option.icon}
                label={option.label}
                selected={slot === option.value}
                onClick={() => setSlot(option.value)}
              />
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-1 text-body-large">{gettext('Tempo')}</span>
            {MINUTES.map((value) => (
              <Chip
                key={value}
                label={value < 60 ? `${value} min` : '1 h'}
                selected={minutes === value}
                onClick={() => setMinutes(minutes === value ? null : value)}
              />
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-body-large">{gettext('Per quante persone')}</span>
            <Stepper
              label={gettext('Per quante persone')}
              value={people}
              min={1}
              max={12}
              onChange={setServings}
            />
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-body-large">{gettext('Cerca anche nei ricettari PDF')}</span>
            <Switch
              label={gettext('Cerca anche nei ricettari PDF')}
              checked={books}
              onChange={setBooks}
            />
          </div>
        </section>

        <ErrorBanner error={suggest.error} />
        <button
          type="button"
          className="btn-filled justify-self-end"
          disabled={!ingredients.length || suggest.isPending}
          onClick={run}
        >
          <Icon name="skillet" size={20} />
          {gettext('Cosa posso cucinare?')}
        </button>

        <div ref={results}>{result && <Results result={result} />}</div>
      </div>
    </Page>
  )
}

/** "Fotografa il frigo": carica la foto, aspetta il lavoro, aggiunge gli alimenti. */
function FridgePhoto({ onFound }: { onFound: (names: string[]) => void }) {
  const scan = useScanFridge()
  const input = useRef<HTMLInputElement>(null)
  const [jobId, setJobId] = useState<string>()
  const { data: job } = useJob(jobId)
  const done = useRef<string>()

  useEffect(() => {
    if (job?.status === 'ready' && done.current !== job.id) {
      done.current = job.id
      onFound(job.result.ingredients ?? [])
    }
  }, [job, onFound])

  const reading = scan.isPending || job?.status === 'queued' || job?.status === 'running'
  const found = job?.status === 'ready' ? (job.result.ingredients ?? []) : []
  return (
    <div className="grid gap-2">
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        hidden
        onChange={async (event) => {
          const files = Array.from(event.target.files ?? []).slice(0, 3)
          event.target.value = ''
          if (!files.length) return
          try {
            const created = await scan.mutateAsync(files)
            setJobId(created.id)
          } catch {
            // Errore sotto.
          }
        }}
      />
      <button
        type="button"
        className="state flex items-center gap-4 rounded-row bg-primary-container p-4 text-left text-on-primary-container"
        onClick={() => input.current?.click()}
        disabled={reading}
      >
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-primary text-on-primary">
          <Icon
            name={reading ? 'hourglass_top' : 'photo_camera'}
            size={24}
            className={clsx(reading && 'animate-pulse')}
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-body-large font-medium">
            {reading ? gettext('Guardo la foto…') : gettext('Fotografa il frigo o la dispensa')}
          </span>
          <span className="block text-body-small opacity-80">
            {job?.status === 'ready'
              ? found.length
                ? interpolate(gettext('Ho trovato %s alimenti: controlla e correggi qui sotto.'), [
                    found.length,
                  ])
                : job.result.problem || gettext('Non ho riconosciuto alimenti.')
              : gettext('Fino a 3 foto. Gli alimenti finiscono nella lista qui sotto.')}
          </span>
        </span>
      </button>
      {job?.status === 'failed' && <ErrorBanner error={job.error} />}
      <ErrorBanner error={scan.error} />
    </div>
  )
}

function Results({ result }: { result: CookSuggestions }) {
  return (
    <div className="grid gap-4">
      <section>
        <h2 className="mb-2 flex items-center gap-2 text-title-large">
          <Icon name="menu_book" size={24} className="text-primary" />
          {gettext('Dal tuo ricettario')}
        </h2>
        {result.matches.length ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {result.matches.map((match) => (
              <MatchCard key={match.recipe.id} match={match} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon="search_off"
            title={gettext('Nessuna ricetta adatta')}
            description={gettext(
              'Aggiungi altri ingredienti, allunga il tempo o cambia pasto. Intanto guarda le idee nuove qui sotto.',
            )}
          />
        )}
      </section>
      {result.job && <Ideas jobId={result.job.id} />}
    </div>
  )
}

function MatchCard({ match }: { match: CookMatch }) {
  const complete = match.missing.length === 0
  return (
    <Link
      to={`/ricette/${match.recipe.id}`}
      state={BACK}
      className="state card-elevated flex gap-3 overflow-hidden bg-surface-container-low"
    >
      <div className="relative w-24 shrink-0">
        <RecipeCover recipe={match.recipe} size={36} />
      </div>
      <div className="min-w-0 flex-1 py-3 pr-3">
        <p className="truncate text-body-large font-medium">{match.recipe.title}</p>
        <p className="text-body-small text-on-surface-variant">
          {match.recipe.total_minutes > 0 && `${formatMinutes(match.recipe.total_minutes)} · `}
          {difficultyLabel(match.recipe.difficulty)}
          {match.recipe.book && ` · ${match.recipe.book.title}`}
        </p>
        <p
          className={clsx(
            'mt-1 inline-flex max-w-full items-center gap-1 rounded-pill px-2.5 py-1 text-label-small',
            complete
              ? 'bg-success-container text-on-success-container'
              : 'bg-warning-container text-on-warning-container',
          )}
        >
          <Icon name={complete ? 'check_circle' : 'shopping_basket'} size={14} />
          <span className="truncate">
            {complete
              ? gettext('Hai tutto')
              : interpolate(gettext('Ti mancano: %s'), [match.missing.join(', ')])}
          </span>
        </p>
      </div>
    </Link>
  )
}

function Ideas({ jobId }: { jobId: string }) {
  const { data: job } = useJob(jobId)
  const working = !job || job.status === 'queued' || job.status === 'running'
  const ideas: RecipeSummary[] = job?.result.ideas ?? []
  return (
    <section>
      <h2 className="mb-2 flex items-center gap-2 text-title-large">
        <Icon name="auto_awesome" size={24} className="text-primary" />
        {gettext('Idee nuove')}
      </h2>
      {working && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-28 rounded-card" />
          <Skeleton className="h-28 rounded-card" />
          <p className="text-body-small text-on-surface-variant sm:col-span-2">
            {gettext('Sto pensando a qualcosa con i tuoi ingredienti…')}
          </p>
        </div>
      )}
      {job?.status === 'failed' && <ErrorBanner error={job.error} />}
      {job?.status === 'ready' && !ideas.length && (
        <p className="text-body-medium text-on-surface-variant">
          {gettext('Questa volta niente idee nuove.')}
        </p>
      )}
      {ideas.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {ideas.map((recipe) => (
            <Link
              key={recipe.id}
              to={`/ricette/${recipe.id}`}
              state={BACK}
              className="state card-elevated flex gap-3 overflow-hidden bg-surface-container-low"
            >
              <div className="relative w-24 shrink-0">
                <RecipeCover recipe={recipe} size={36} />
              </div>
              <div className="min-w-0 flex-1 py-3 pr-3">
                <p className="truncate text-body-large font-medium">{recipe.title}</p>
                <p className="text-body-small text-on-surface-variant">
                  {recipe.total_minutes > 0 && `${formatMinutes(recipe.total_minutes)} · `}
                  {difficultyLabel(recipe.difficulty)}
                </p>
                <p className="mt-1 inline-flex items-center gap-1 text-label-small text-primary">
                  <Icon name="bookmark_add" size={14} />
                  {gettext('Aprila per salvarla')}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
