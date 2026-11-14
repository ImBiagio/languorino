// Condivisione delle ricette (ADR 0012): un link `/r/<token>` che si apre
// senza login; chi ha un account copia la ricetta nel suo ricettario.

import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  useCopySharedRecipe,
  useShareRecipe,
  useSharedRecipe,
  useUnshareRecipe,
} from '../../api/hooks'
import { FoodPattern, RecipeCover } from '../../components/illustrations'
import { Chip, ErrorBanner, Icon, Modal, Skeleton } from '../../components/ui'
import { useAuth } from '../../lib/auth'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { Recipe } from '../../lib/types'
import { ALLERGEN_OPTIONS } from '../profile/options'
import { NutritionFacts } from './NutritionCard'
import { difficultyLabel, formatMinutes, formatQuantity } from './options'

export function shareUrl(token: string): string {
  return `${window.location.origin}/r/${token}`
}

/* ------------------------------------------- dialogo nel dettaglio ---- */

export function ShareDialog({
  recipe,
  open,
  onClose,
}: {
  recipe: Recipe
  open: boolean
  onClose: () => void
}) {
  const share = useShareRecipe()
  const unshare = useUnshareRecipe()
  const [copied, setCopied] = useState(false)
  const url = recipe.share_token ? shareUrl(recipe.share_token) : ''
  const busy = share.isPending || unshare.isPending

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // Appunti non disponibili: il link resta selezionabile a mano.
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={gettext('Condividi la ricetta')}>
      <div className="grid gap-4">
        {recipe.share_token ? (
          <>
            <p className="text-body-medium text-on-surface-variant">
              {gettext(
                'Chi ha il link vede la ricetta anche senza account; con un account la copia nel suo ricettario.',
              )}
            </p>
            <input
              className="field-input rounded-row bg-surface-container-high px-4 py-3"
              readOnly
              value={url}
              aria-label={gettext('Link della ricetta')}
              onFocus={(event) => event.target.select()}
            />
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-filled" onClick={copy}>
                <Icon name={copied ? 'check' : 'content_copy'} size={20} />
                {copied ? gettext('Copiato') : gettext('Copia il link')}
              </button>
              {typeof navigator.share === 'function' && (
                <button
                  type="button"
                  className="btn-tonal"
                  onClick={() =>
                    navigator.share({ title: recipe.title, url }).catch(() => undefined)
                  }
                >
                  <Icon name="share" size={20} />
                  {gettext('Invia…')}
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2 border-t border-outline-variant pt-3">
              <button
                type="button"
                className="btn-text btn-sm"
                disabled={busy}
                onClick={() => share.mutate({ id: recipe.id, renew: true })}
              >
                <Icon name="autorenew" size={18} />
                {gettext('Nuovo link (spegne il vecchio)')}
              </button>
              <button
                type="button"
                className="btn-text btn-sm text-error"
                disabled={busy}
                onClick={() => unshare.mutate(recipe.id)}
              >
                <Icon name="link_off" size={18} />
                {gettext('Spegni il link')}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="text-body-medium text-on-surface-variant">
              {gettext(
                'Crea un link da mandare a chi vuoi: vede la ricetta anche senza account e può copiarla nel suo ricettario. Puoi spegnerlo quando vuoi.',
              )}
            </p>
            <button
              type="button"
              className="btn-filled justify-self-start"
              disabled={busy}
              onClick={() => share.mutate({ id: recipe.id })}
            >
              <Icon name="link" size={20} />
              {gettext('Crea il link')}
            </button>
          </>
        )}
        <ErrorBanner error={share.error ?? unshare.error} />
      </div>
    </Modal>
  )
}

/* --------------------------------------------------- /r/:token ---- */

export function SharedRecipePage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { user, ready } = useAuth()
  const {
    data: recipe,
    error,
    isPending,
  } = useSharedRecipe(token, ready ? (user ? String(user.id) : 'anon') : undefined)
  const copy = useCopySharedRecipe()
  const back = `/r/${token}`

  return (
    <div className="min-h-dvh bg-surface">
      <header className="relative overflow-hidden bg-primary text-on-primary">
        <FoodPattern tone="dark" opacity={0.3} />
        <div className="relative mx-auto flex max-w-4xl items-center gap-3 px-5 py-3">
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo-mark.svg" alt="" width={32} height={32} className="h-8 w-8" />
            <span className="text-title-medium font-medium">Languorino</span>
          </Link>
        </div>
      </header>

      <main className="mx-auto grid max-w-4xl gap-5 px-5 pb-10 pt-5">
        {isPending && <Skeleton className="h-72 rounded-card" />}
        {error && (
          <section className="grid justify-items-center gap-2 rounded-card bg-surface-container-low px-6 py-10 text-center">
            <Icon name="link_off" size={40} className="text-on-surface-variant" />
            <p className="text-title-medium">{gettext('Questo link non funziona più')}</p>
            <p className="max-w-md text-body-medium text-on-surface-variant">
              {gettext('Chi te l’ha mandato potrebbe averlo spento o sostituito con uno nuovo.')}
            </p>
          </section>
        )}
        {recipe && (
          <>
            <div className="relative h-56 overflow-hidden rounded-panel md:h-72">
              <RecipeCover recipe={recipe} size={96} />
            </div>
            <header>
              <h1 className="text-[28px] font-medium leading-9 md:text-headline-small">
                {recipe.title}
              </h1>
              {recipe.author && (
                <p className="mt-1 text-body-medium text-on-surface-variant">
                  {interpolate(gettext('Condivisa da %s'), [recipe.author])}
                </p>
              )}
              {recipe.description && (
                <p className="mt-2 whitespace-pre-line text-body-large text-on-surface-variant">
                  {recipe.description}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                {recipe.total_minutes > 0 && (
                  <Chip
                    variant="assist"
                    icon="schedule"
                    label={formatMinutes(recipe.total_minutes)}
                  />
                )}
                <Chip
                  variant="assist"
                  icon="signal_cellular_alt"
                  label={difficultyLabel(recipe.difficulty)}
                />
                <Chip
                  variant="assist"
                  icon="group"
                  label={interpolate(ngettext('%s porzione', '%s porzioni', recipe.servings), [
                    recipe.servings,
                  ])}
                />
              </div>
              {recipe.allergens.length > 0 && (
                <p className="mt-3 flex flex-wrap items-center gap-1.5 text-body-small text-on-surface-variant">
                  <Icon name="health_and_safety" size={16} />
                  {interpolate(gettext('Contiene: %s'), [
                    ALLERGEN_OPTIONS.filter((option) => recipe.allergens.includes(option.value))
                      .map((option) => option.label.toLowerCase())
                      .join(', '),
                  ])}
                </p>
              )}
            </header>

            <section className="flex flex-wrap items-center gap-3 rounded-card bg-primary-container p-4 text-on-primary-container">
              <Icon name="menu_book" size={24} />
              {!ready ? null : recipe.is_mine ? (
                <p className="min-w-0 flex-1 text-body-medium">
                  {gettext('È una tua ricetta: così la vede chi ha il link.')}
                </p>
              ) : user ? (
                <>
                  <p className="min-w-0 flex-1 text-body-medium">
                    {gettext('Ti piace? Copiala nel tuo ricettario e usala nei tuoi piani.')}
                  </p>
                  <button
                    type="button"
                    className="btn-filled"
                    disabled={copy.isPending}
                    onClick={async () => {
                      try {
                        const created = await copy.mutateAsync(token!)
                        navigate(`/ricette/${created.id}`)
                      } catch {
                        // Errore sotto.
                      }
                    }}
                  >
                    <Icon name="bookmark_add" size={20} />
                    {gettext('Copia nel mio ricettario')}
                  </button>
                </>
              ) : (
                <>
                  <p className="min-w-0 flex-1 text-body-medium">
                    {gettext(
                      'Con Languorino la copi nel tuo ricettario, ci componi il piano della settimana e fai la spesa.',
                    )}
                  </p>
                  <Link to={`/registrati?next=${encodeURIComponent(back)}`} className="btn-filled">
                    {gettext('Registrati')}
                  </Link>
                  <Link to={`/accedi?next=${encodeURIComponent(back)}`} className="btn-text">
                    {gettext('Accedi')}
                  </Link>
                </>
              )}
            </section>
            <ErrorBanner error={copy.error} />

            <div className="grid gap-5 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
              <section className="rounded-card bg-surface-container-low p-5">
                <h2 className="mb-2 text-title-medium">{gettext('Ingredienti')}</h2>
                <ul className="divide-y divide-outline-variant">
                  {recipe.ingredients.map((line) => (
                    <li key={line.id} className="flex items-baseline gap-3 py-2.5">
                      <span className="min-w-0 flex-1 text-body-large">
                        {line.ingredient.name}
                        {line.note && (
                          <span className="text-on-surface-variant">, {line.note}</span>
                        )}
                        {line.optional && (
                          <span className="ml-2 text-label-small text-on-surface-variant">
                            {gettext('facoltativo')}
                          </span>
                        )}
                      </span>
                      <span className="amount shrink-0 text-body-medium text-on-surface-variant">
                        {formatQuantity(line.quantity, line.unit)}
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
            {(recipe.kcal !== null || recipe.protein_g !== null) && (
              <section className="rounded-card bg-surface-container-low p-5">
                <h2 className="mb-3 text-title-medium">{gettext('Calorie e macro')}</h2>
                <NutritionFacts nutrition={recipe} servings={recipe.servings} />
              </section>
            )}
          </>
        )}
      </main>
    </div>
  )
}
