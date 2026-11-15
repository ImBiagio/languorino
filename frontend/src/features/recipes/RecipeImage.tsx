// Immagine della ricetta (ADR 0011): foto vera caricata a mano, che vince
// sempre, o disegnata dall'AI su richiesta (via cornhub, ADR 0021); senza, il disegno per categoria.

import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import {
  keys,
  useDrawRecipeImage,
  useJob,
  useRemoveRecipeImage,
  useUploadRecipeImage,
} from '../../api/hooks'
import { AiKeyIcon, useAiGate } from '../../components/Ai'
import { AiCost } from '../../components/AiCost'
import { RecipeCover } from '../../components/illustrations'
import { Icon, IconButton, Modal } from '../../components/ui'
import { gettext } from '../../lib/i18n'
import type { Recipe } from '../../lib/types'

export function RecipeHeroImage({ recipe }: { recipe: Recipe }) {
  const client = useQueryClient()
  const upload = useUploadRecipeImage()
  const remove = useRemoveRecipeImage()
  const draw = useDrawRecipeImage()
  const [open, setOpen] = useState(false)
  const [jobId, setJobId] = useState<string>()
  const [dismissed, setDismissed] = useState<unknown>(null)
  const { data: job } = useJob(jobId)
  const input = useRef<HTMLInputElement>(null)
  const drawing = draw.isPending || job?.status === 'queued' || job?.status === 'running'
  const busy = drawing || upload.isPending || remove.isPending

  // Disegno pronto: si ricarica la ricetta (e le card) con l'immagine nuova.
  useEffect(() => {
    if (job?.status === 'ready') {
      void client.invalidateQueries({ queryKey: keys.recipe(recipe.id) })
      void client.invalidateQueries({ queryKey: [...keys.recipes, 'list'] })
    }
  }, [job?.status, client, recipe.id])

  const failure =
    upload.error ?? remove.error ?? draw.error ?? (job?.status === 'failed' ? job.error : null)
  const error = failure && failure !== dismissed ? failure : null
  const message = error instanceof Error ? error.message : error ? String(error) : ''

  // Ogni azione nuova fa ripartire da capo: via l'errore di quella prima.
  const close = (then: () => void) => {
    setOpen(false)
    setDismissed(failure)
    then()
  }

  return (
    <>
      <RecipeCover recipe={recipe} size={96} />
      {drawing && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/40 text-white">
          <Icon name="brush" size={36} className="animate-pulse" />
          <p className="text-body-large font-medium">{gettext('Disegno il piatto…')}</p>
        </div>
      )}
      <div className="absolute bottom-3 right-3">
        <IconButton
          icon={recipe.image ? 'image' : 'add_a_photo'}
          size="md"
          label={gettext('Immagine della ricetta')}
          onClick={() => setOpen(true)}
          disabled={busy}
          className="bg-surface text-on-surface shadow-fab"
        />
      </div>
      {error && (
        <div
          role="alert"
          className="absolute inset-x-3 bottom-3 mr-14 flex items-start gap-2 rounded-row bg-error-container px-3 py-2 text-body-small text-on-error-container"
        >
          <Icon name="error" size={18} />
          <span className="min-w-0 flex-1">{message}</span>
          <button
            type="button"
            aria-label={gettext('Chiudi')}
            onClick={() => setDismissed(failure)}
          >
            <Icon name="close" size={18} />
          </button>
        </div>
      )}
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (!file) return
          draw.reset()
          setJobId(undefined)
          upload.mutate({ id: recipe.id, file })
        }}
      />
      <Modal open={open} onClose={() => setOpen(false)} title={gettext('Immagine della ricetta')}>
        <div className="grid gap-2">
          <Action
            icon="photo_camera"
            tone="bg-primary text-on-primary"
            title={recipe.image ? gettext('Cambia con una foto') : gettext('Carica una foto')}
            hint={gettext('Il piatto vero, scattato o dalla galleria: vince sempre')}
            onClick={() => close(() => input.current?.click())}
          />
          {open && recipe.image_source !== 'photo' && (
            <DrawAction
              title={
                recipe.image ? gettext('Fallo ridisegnare') : gettext('Fallo disegnare all’AI')
              }
              onClick={() =>
                close(async () => {
                  try {
                    const started = await draw.mutateAsync(recipe.id)
                    setJobId(started.id)
                  } catch {
                    // Errore sull'immagine.
                  }
                })
              }
            />
          )}
          {open && recipe.image_source !== 'photo' && (
            <div className="px-1">
              <AiCost feature="recipe_image" />
            </div>
          )}
          {recipe.image && (
            <Action
              icon="hide_image"
              tone="bg-surface-container-highest text-on-surface"
              title={gettext('Togli l’immagine')}
              hint={gettext('Torna il disegno della categoria')}
              onClick={() => close(() => remove.mutate(recipe.id))}
            />
          )}
        </div>
      </Modal>
    </>
  )
}

/**
 * "Fallo disegnare": funzione grande (immagine, chiave dell'utente). Sta in un
 * componente a parte cosi' la stima si chiede solo a finestra aperta.
 */
function DrawAction({ title, onClick }: { title: string; onClick: () => void }) {
  const gate = useAiGate('recipe_image')
  return (
    <Action
      icon="auto_awesome"
      tone="bg-tertiary-container text-on-tertiary-container"
      title={title}
      hint={gettext('Un’immagine del piatto creata dall’AI, in meno di un minuto')}
      onClick={onClick}
      disabled={!gate.allowed}
      aiKey={gate.large}
    />
  )
}

function Action({
  icon,
  tone,
  title,
  hint,
  onClick,
  disabled,
  aiKey,
}: {
  icon: string
  tone: string
  title: string
  hint: string
  onClick: () => void
  disabled?: boolean
  /** Funzione AI grande: il simbolo della chiave accanto al titolo. */
  aiKey?: boolean
}) {
  return (
    <button
      type="button"
      className="state flex items-center gap-4 rounded-row bg-surface-container-low p-4 text-left disabled:cursor-not-allowed disabled:opacity-40"
      onClick={onClick}
      disabled={disabled}
    >
      <span
        className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] ${tone}`}
      >
        <Icon name={icon} size={24} />
      </span>
      <span>
        <span className="flex items-center gap-1.5 text-body-large font-medium">
          {title}
          {aiKey && <AiKeyIcon />}
        </span>
        <span className="block text-body-small text-on-surface-variant">{hint}</span>
      </span>
    </button>
  )
}
