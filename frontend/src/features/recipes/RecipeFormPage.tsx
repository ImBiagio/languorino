import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { useRecipe, useSaveRecipe } from '../../api/hooks'
import { Page } from '../../components/Layout'
import { ErrorBanner, Icon, IconButton, Skeleton } from '../../components/ui'
import { ApiError } from '../../lib/api'
import { gettext } from '../../lib/i18n'
import type { Recipe } from '../../lib/types'
import { RecipeEditor, draftFromRecipe, payloadFrom } from './RecipeEditor'
import type { Draft } from './RecipeEditor'

/** Nuova ricetta (`/ricette/nuova`) o modifica (`/ricette/:id/modifica`). */
export function RecipeFormPage() {
  const { recipeId } = useParams()
  const { data: recipe, error } = useRecipe(recipeId)
  if (recipeId && error) return <ErrorBanner error={error} />
  if (recipeId && !recipe) return <Skeleton className="m-5 h-72 rounded-card md:m-8" />
  return <RecipeForm key={recipe?.id ?? 'new'} recipe={recipe} />
}

function RecipeForm({ recipe }: { recipe?: Recipe }) {
  const navigate = useNavigate()
  const save = useSaveRecipe()
  const [draft, setDraft] = useState<Draft>(() => draftFromRecipe(recipe))
  const errors = save.error instanceof ApiError ? save.error.fieldErrors() : {}
  const back = recipe ? `/ricette/${recipe.id}` : '/ricette'

  const submit = async () => {
    try {
      const saved = await save.mutateAsync({ id: recipe?.id, ...payloadFrom(draft) })
      navigate(`/ricette/${saved.id}`, { replace: true })
    } catch {
      // L'errore resta in save.error e si vede in fondo e sui campi.
    }
  }

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="mb-5 flex items-center gap-3">
        <IconButton
          icon="close"
          size="md"
          label={gettext('Annulla')}
          onClick={() => navigate(back)}
        />
        <h1 className="flex-1 text-title-large">
          {recipe ? gettext('Modifica ricetta') : gettext('Nuova ricetta')}
        </h1>
        <button
          type="button"
          className="btn-filled btn-sm"
          disabled={save.isPending || !draft.title.trim()}
          onClick={submit}
        >
          {gettext('Salva')}
        </button>
      </header>

      <div className="grid gap-4">
        <RecipeEditor draft={draft} setDraft={setDraft} errors={errors} autoFocus={!recipe} />
        <ErrorBanner error={save.error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-text" onClick={() => navigate(back)}>
            {gettext('Annulla')}
          </button>
          <button
            type="button"
            className="btn-filled"
            disabled={save.isPending || !draft.title.trim()}
            onClick={submit}
          >
            <Icon name="check" size={20} />
            {gettext('Salva la ricetta')}
          </button>
        </div>
      </div>
    </Page>
  )
}
