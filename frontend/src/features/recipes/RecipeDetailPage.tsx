import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useDeleteRecipe, useRecipe, useSaveToCookbook } from '../../api/hooks'
import { useConfirm } from '../../components/ConfirmDialog'
import { Page } from '../../components/Layout'
import { RecipeArt } from '../../components/illustrations'
import { Chip, ErrorBanner, Icon, IconButton, Skeleton, Stepper } from '../../components/ui'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { Recipe } from '../../lib/types'
import { MEAL_OPTIONS, preferenceLabel } from '../profile/options'
import { difficultyLabel, formatMinutes, formatQuantity } from './options'

export function RecipeDetailPage() {
  const { recipeId } = useParams()
  const { data: recipe, error } = useRecipe(recipeId)
  if (error) {
    return (
      <Page className="px-5 pt-5 md:px-8 md:pt-8">
        <ErrorBanner error={error} />
      </Page>
    )
  }
  if (!recipe) return <Skeleton className="m-5 h-72 rounded-card md:m-8" />
  // La chiave azzera le porzioni scelte quando si passa a un'altra ricetta.
  return <RecipeView key={recipe.id} recipe={recipe} />
}

function RecipeView({ recipe }: { recipe: Recipe }) {
  const navigate = useNavigate()
  const confirm = useConfirm()
  const remove = useDeleteRecipe()
  const save = useSaveToCookbook()
  // Una ricetta di un ricettario PDF non ancora salvata: si torna al ricettario.
  const fromBook = recipe.book && !recipe.in_cookbook
  // Scritta dall'LLM per un piano e non ancora salvata.
  const fromPlan = !recipe.book && !recipe.in_cookbook && recipe.source === 'plan'
  const backTo = fromBook
    ? `/ricette/ricettari/${recipe.book!.id}`
    : fromPlan
      ? '/piano'
      : '/ricette'
  const [servings, setServings] = useState(recipe.servings)
  const factor = servings / recipe.servings
  const restrictions = recipe.warnings.filter((item) => item.kind !== 'dislike')
  const dislikes = recipe.warnings.filter((item) => item.kind === 'dislike')
  const slots = MEAL_OPTIONS.filter((option) => recipe.meal_slots.includes(option.value))

  return (
    <Page className="pb-8">
      <div className="relative h-44 overflow-hidden md:mx-8 md:mt-8 md:h-56 md:rounded-panel">
        <RecipeArt category={recipe.main_category} size={96} />
        <div className="absolute inset-x-0 top-0 flex items-center justify-between p-3">
          <IconButton
            icon="arrow_back"
            size="md"
            label={gettext('Ricette')}
            onClick={() => navigate(backTo)}
            className="bg-surface text-on-surface shadow-fab"
          />
          <div className="flex gap-2">
            <IconButton
              icon="edit"
              size="md"
              label={gettext('Modifica')}
              onClick={() => navigate(`/ricette/${recipe.id}/modifica`)}
              className="bg-surface text-on-surface shadow-fab"
            />
            <IconButton
              icon="delete"
              size="md"
              label={gettext('Elimina')}
              onClick={async () => {
                const ok = await confirm({
                  title: gettext('Eliminare la ricetta?'),
                  message: interpolate(gettext('“%s” sparirà dal ricettario.'), [recipe.title]),
                  confirmLabel: gettext('Elimina'),
                  icon: 'delete',
                  destructive: true,
                })
                if (!ok) return
                await remove.mutateAsync(recipe.id)
                navigate(backTo, { replace: true })
              }}
              className="bg-surface text-error shadow-fab"
            />
          </div>
        </div>
      </div>

      <div className="grid gap-5 px-5 pt-5 md:px-8">
        <header>
          <h1 className="text-[28px] font-medium leading-9 md:text-headline-small">
            {recipe.title}
          </h1>
          {recipe.description && (
            <p className="mt-2 whitespace-pre-line text-body-large text-on-surface-variant">
              {recipe.description}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {recipe.total_minutes > 0 && (
              <Fact icon="schedule">
                {formatMinutes(recipe.total_minutes)}
                {recipe.cook_minutes > 0 && recipe.prep_minutes > 0 && (
                  <span className="text-on-surface-variant">
                    {' · '}
                    {interpolate(gettext('%s di cottura'), [formatMinutes(recipe.cook_minutes)])}
                  </span>
                )}
              </Fact>
            )}
            <Fact icon="signal_cellular_alt">{difficultyLabel(recipe.difficulty)}</Fact>
            {recipe.keeps_days !== null && (
              <Fact icon="kitchen">
                {recipe.keeps_days === 0
                  ? gettext('Da mangiare subito')
                  : interpolate(
                      ngettext('In frigo %s giorno', 'In frigo %s giorni', recipe.keeps_days),
                      [recipe.keeps_days],
                    )}
              </Fact>
            )}
            {recipe.freezable && <Fact icon="ac_unit">{gettext('Si congela')}</Fact>}
            {slots.map((slot) => (
              <Fact key={slot.value} icon={slot.icon}>
                {slot.label}
              </Fact>
            ))}
          </div>
        </header>

        {fromBook && (
          <section className="flex flex-wrap items-center gap-3 rounded-row bg-tertiary-container px-4 py-3 text-on-tertiary-container">
            <Icon name="library_books" size={22} />
            <p className="min-w-0 flex-1 text-body-medium">
              {interpolate(
                gettext('Dal ricettario “%s”, letta automaticamente e non ancora rivista.'),
                [recipe.book!.title],
              )}
            </p>
            <button
              type="button"
              className="btn-filled btn-sm"
              disabled={save.isPending}
              onClick={() => save.mutate(recipe.id)}
            >
              <Icon name="bookmark_add" size={18} />
              {gettext('Salva nel mio ricettario')}
            </button>
          </section>
        )}
        {fromPlan && (
          <section className="flex flex-wrap items-center gap-3 rounded-row bg-tertiary-container px-4 py-3 text-on-tertiary-container">
            <Icon name="auto_awesome" size={22} />
            <p className="min-w-0 flex-1 text-body-medium">
              {gettext('Scritta per il tuo piano: non è ancora nel tuo ricettario.')}
            </p>
            <button
              type="button"
              className="btn-filled btn-sm"
              disabled={save.isPending}
              onClick={() => save.mutate(recipe.id)}
            >
              <Icon name="bookmark_add" size={18} />
              {gettext('Salva nel mio ricettario')}
            </button>
          </section>
        )}
        {recipe.book && recipe.in_cookbook && (
          <Link
            to={`/ricette/ricettari/${recipe.book.id}`}
            className="inline-flex w-fit items-center gap-1.5 text-body-small text-primary"
          >
            <Icon name="library_books" size={16} />
            {interpolate(gettext('Dal ricettario “%s”'), [recipe.book.title])}
          </Link>
        )}
        <ErrorBanner error={save.error} />

        {restrictions.length > 0 && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-row bg-error-container px-4 py-3 text-on-error-container"
          >
            <Icon name="warning" size={22} filled />
            <div>
              <p className="text-body-large font-medium">
                {gettext('Attenzione: contiene cose che non puoi mangiare')}
              </p>
              <p className="text-body-medium">{restrictions.map(preferenceLabel).join(', ')}</p>
            </div>
          </div>
        )}
        {dislikes.length > 0 && (
          <p className="flex items-center gap-2 rounded-row bg-surface-container px-4 py-3 text-body-medium text-on-surface-variant">
            <Icon name="thumb_down" size={18} />
            {interpolate(gettext('Contiene cose che non ti piacciono: %s'), [
              dislikes.map((item) => item.label).join(', '),
            ])}
          </p>
        )}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <section className="rounded-card bg-surface-container-low p-5">
            <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-title-medium">{gettext('Ingredienti')}</h2>
              <Stepper
                label={gettext('Porzioni')}
                value={servings}
                min={1}
                max={50}
                onChange={setServings}
                format={(value) =>
                  interpolate(ngettext('%s porzione', '%s porzioni', value), [value])
                }
              />
            </header>
            {recipe.ingredients.length === 0 ? (
              <p className="text-body-medium text-on-surface-variant">
                {gettext('Nessun ingrediente scritto.')}
              </p>
            ) : (
              <ul className="divide-y divide-outline-variant">
                {recipe.ingredients.map((line) => (
                  <li key={line.id} className="flex items-baseline gap-3 py-2.5">
                    <span className="min-w-0 flex-1 text-body-large">
                      {line.ingredient.name}
                      {line.note && <span className="text-on-surface-variant">, {line.note}</span>}
                      {line.optional && (
                        <span className="ml-2 text-label-small text-on-surface-variant">
                          {gettext('facoltativo')}
                        </span>
                      )}
                    </span>
                    <span className="amount shrink-0 text-body-medium text-on-surface-variant">
                      {formatQuantity(line.quantity, line.unit, factor)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-card bg-surface-container-low p-5">
            <h2 className="mb-3 text-title-medium">{gettext('Preparazione')}</h2>
            {recipe.steps.length === 0 ? (
              <p className="text-body-medium text-on-surface-variant">
                {gettext('Nessun passo scritto.')}
              </p>
            ) : (
              <ol className="grid gap-4">
                {recipe.steps.map((step, index) => (
                  <li key={index} className="flex gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-pill bg-primary text-body-medium font-medium text-on-primary">
                      {index + 1}
                    </span>
                    <p className="whitespace-pre-line pt-1 text-body-large">{step}</p>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>

        {recipe.tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {recipe.tags.map((tag) => (
              <Chip key={tag} variant="assist" icon="sell" label={tag} />
            ))}
          </div>
        )}

        <Link to={`/ricette/${recipe.id}/modifica`} className="btn-tonal w-fit">
          <Icon name="edit" size={20} />
          {gettext('Modifica la ricetta')}
        </Link>
        <ErrorBanner error={remove.error} />
      </div>
    </Page>
  )
}

function Fact({ icon, children }: { icon: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-pill bg-surface-container-high px-3 py-1.5 text-body-medium">
      <Icon name={icon} size={18} className="text-primary" />
      {children}
    </span>
  )
}
