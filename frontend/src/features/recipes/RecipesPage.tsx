import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useRecipes, useTags } from '../../api/hooks'
import { Page, PageHeader } from '../../components/Layout'
import { CookbookIllustration, RecipeArt } from '../../components/illustrations'
import { Chip, EmptyState, ErrorBanner, Fab, Icon, Skeleton } from '../../components/ui'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { RecipeFilters, RecipeSummary } from '../../lib/types'
import { preferenceLabel } from '../profile/options'
import { difficultyLabel, formatMinutes } from './options'

/** Le ricette "veloci" del filtro rapido: quelle da fare in mezz'ora. */
const QUICK_MINUTES = 30

/** Il ricettario: ricerca, filtri rapidi, griglia di card. */
export function RecipesPage() {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [quick, setQuick] = useState(false)

  // La ricerca parte quando si smette di scrivere, non a ogni lettera.
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(text.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [text])

  const filters: RecipeFilters = {
    q: query,
    tag: tags,
    max_minutes: quick ? QUICK_MINUTES : undefined,
  }
  const { data, error, isPending } = useRecipes(filters)
  const { data: allTags } = useTags()
  const usedTags = (allTags ?? []).filter((tag) => tag.recipe_count > 0)
  const filtering = Boolean(query || tags.length || quick)
  const recipes = data?.results ?? []

  return (
    <Page>
      <PageHeader
        title={gettext('Ricette')}
        subtitle={
          data?.count && !filtering
            ? interpolate(
                ngettext('%s ricetta nel ricettario', '%s ricette nel ricettario', data.count),
                [data.count],
              )
            : gettext('Il tuo ricettario')
        }
      />
      <div className="grid gap-4 px-5 md:px-8">
        <label className="flex items-center gap-3 rounded-pill bg-surface-container-high px-5 py-3 focus-within:ring-2 focus-within:ring-primary">
          <Icon name="search" size={22} className="text-on-surface-variant" />
          <input
            className="min-w-0 flex-1 bg-transparent text-body-large outline-none placeholder:text-on-surface-variant"
            placeholder={gettext('Cerca per nome, ingrediente o tag')}
            value={text}
            onChange={(event) => setText(event.target.value)}
            type="search"
          />
        </label>

        {(usedTags.length > 0 || recipes.length > 0 || quick) && (
          <div className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5 md:mx-0 md:flex-wrap md:px-0">
            <Chip
              icon={quick ? 'check' : 'bolt'}
              label={interpolate(gettext('Pronte in %s min'), [QUICK_MINUTES])}
              selected={quick}
              onClick={() => setQuick(!quick)}
            />
            {usedTags.map((tag) => {
              const active = tags.includes(tag.name)
              return (
                <Chip
                  key={tag.id}
                  icon={active ? 'check' : 'sell'}
                  label={tag.name}
                  selected={active}
                  onClick={() =>
                    setTags(active ? tags.filter((name) => name !== tag.name) : [...tags, tag.name])
                  }
                />
              )
            })}
          </div>
        )}

        <ErrorBanner error={error} />

        {isPending && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton key={index} className="h-52 rounded-card" />
            ))}
          </div>
        )}

        {!isPending && recipes.length === 0 && !filtering && (
          <EmptyState
            illustration={<CookbookIllustration />}
            title={gettext('Il ricettario è vuoto')}
            description={gettext(
              'Scrivi le ricette che fai di solito: il piano alimentare partirà da queste.',
            )}
            action={
              <Link to="/ricette/nuova" className="btn-filled">
                <Icon name="add" size={20} />
                {gettext('Scrivi la prima ricetta')}
              </Link>
            }
          />
        )}

        {!isPending && recipes.length === 0 && filtering && (
          <EmptyState
            icon="search_off"
            title={gettext('Nessuna ricetta trovata')}
            description={gettext('Prova a togliere un filtro o a cercare un’altra parola.')}
          />
        )}

        {recipes.length > 0 && (
          <div
            className={clsx(
              'grid grid-cols-2 gap-3 transition-opacity sm:grid-cols-3 lg:grid-cols-4',
              data && isPending && 'opacity-60',
            )}
          >
            {recipes.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} />
            ))}
          </div>
        )}
      </div>
      <Fab icon="add" label={gettext('Nuova ricetta')} onClick={() => navigate('/ricette/nuova')} />
    </Page>
  )
}

function RecipeCard({ recipe }: { recipe: RecipeSummary }) {
  const restrictions = recipe.warnings.filter((item) => item.kind !== 'dislike')
  const dislikes = recipe.warnings.filter((item) => item.kind === 'dislike')
  return (
    <Link
      to={`/ricette/${recipe.id}`}
      className="state card-elevated flex flex-col overflow-hidden bg-surface-container-low"
    >
      <div className="relative h-28 sm:h-32">
        <RecipeArt category={recipe.main_category} size={56} />
        {restrictions.length > 0 && (
          <span
            className="absolute left-2 top-2 inline-flex max-w-[calc(100%-1rem)] items-center gap-1 rounded-pill bg-error px-2.5 py-1 text-label-small text-white"
            title={restrictions.map(preferenceLabel).join(', ')}
          >
            <Icon name="warning" size={14} filled />
            <span className="truncate">{restrictions.map(preferenceLabel).join(', ')}</span>
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-3.5">
        <h2 className="line-clamp-2 text-body-large font-medium">{recipe.title}</h2>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body-small text-on-surface-variant">
          {recipe.total_minutes > 0 && (
            <span className="inline-flex items-center gap-1">
              <Icon name="schedule" size={16} />
              {formatMinutes(recipe.total_minutes)}
            </span>
          )}
          <span className="inline-flex items-center gap-1">
            <Icon name="signal_cellular_alt" size={16} />
            {difficultyLabel(recipe.difficulty)}
          </span>
        </p>
        {dislikes.length > 0 && (
          <p className="inline-flex items-center gap-1 text-body-small text-on-surface-variant">
            <Icon name="thumb_down" size={14} />
            <span className="truncate">{dislikes.map((item) => item.label).join(', ')}</span>
          </p>
        )}
        {recipe.tags.length > 0 && (
          <p className="mt-auto truncate pt-1 text-label-small text-primary">
            {recipe.tags.map((tag) => `#${tag}`).join(' ')}
          </p>
        )}
      </div>
    </Link>
  )
}
