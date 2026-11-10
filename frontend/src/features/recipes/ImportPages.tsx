// Import di ricette da foto e PDF (progettazione 4.2, ADR 0005): si caricano i
// file, l'LLM li legge in un job, si rivedono le bozze nello stesso form delle
// ricette scritte a mano e solo allora entrano nel ricettario.

import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  useConfirmImport,
  useDiscardJob,
  useJob,
  useRetryJob,
  useStartImport,
} from '../../api/hooks'
import { useConfirm } from '../../components/ConfirmDialog'
import { Page } from '../../components/Layout'
import { CookbookIllustration, FoodPattern } from '../../components/illustrations'
import { EmptyState, ErrorBanner, Icon, IconButton, Skeleton, Switch } from '../../components/ui'
import { ApiError } from '../../lib/api'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { Job } from '../../lib/types'
import { useBookUploader } from './BooksPages'
import { RecipeEditor, draftFromImport, payloadFrom } from './RecipeEditor'
import type { Draft } from './RecipeEditor'

const MAX_FILES = 8

/* ------------------------------------------------------- caricamento ---- */

export function ImportPage() {
  const navigate = useNavigate()
  const start = useStartImport()
  const [files, setFiles] = useState<File[]>([])
  const photos = useRef<HTMLInputElement>(null)
  // Un PDF diventa un ricettario da sfogliare (ADR 0006), non una revisione.
  const uploader = useBookUploader()

  const add = (list: FileList | null) => {
    if (!list) return
    setFiles((current) => [...current, ...Array.from(list)].slice(0, MAX_FILES))
  }

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="mb-5 flex items-center gap-3">
        <IconButton
          icon="arrow_back"
          size="md"
          label={gettext('Ricette')}
          onClick={() => navigate('/ricette')}
        />
        <h1 className="flex-1 text-title-large">{gettext('Importa ricette')}</h1>
      </header>

      <div className="grid gap-4">
        <section className="relative overflow-hidden rounded-panel bg-primary-container p-6 text-on-primary-container">
          {/* I doodle solo a destra: a sinistra c'e' il testo. */}
          <div className="absolute inset-y-0 right-0 w-1/2 [mask-image:linear-gradient(to_right,transparent,black)]">
            <FoodPattern opacity={0.6} />
          </div>
          <div className="relative max-w-xl">
            <h2 className="text-title-large">{gettext('Dalla carta al ricettario')}</h2>
            <p className="mt-1 text-body-large">
              {gettext(
                'Fotografa le ricette scritte a mano: le leggo io, tu controlli e confermi. Un PDF diventa un ricettario da sfogliare.',
              )}
            </p>
          </div>
        </section>

        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            className="state flex items-center gap-4 rounded-card bg-surface-container-low p-5 text-left"
            onClick={() => photos.current?.click()}
          >
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[16px] bg-primary text-on-primary">
              <Icon name="photo_camera" size={26} />
            </span>
            <span>
              <span className="block text-body-large font-medium">{gettext('Foto')}</span>
              <span className="block text-body-small text-on-surface-variant">
                {gettext('Scatta o scegli dalla galleria, anche più pagine')}
              </span>
            </span>
          </button>
          <button
            type="button"
            className="state flex items-center gap-4 rounded-card bg-surface-container-low p-5 text-left"
            onClick={uploader.open}
            disabled={uploader.upload.isPending}
          >
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[16px] bg-accent text-white">
              <Icon name="picture_as_pdf" size={26} />
            </span>
            <span>
              <span className="block text-body-large font-medium">{gettext('PDF')}</span>
              <span className="block text-body-small text-on-surface-variant">
                {uploader.upload.isPending
                  ? gettext('Carico…')
                  : gettext('Un ricettario intero: lo leggo pagina per pagina')}
              </span>
            </span>
          </button>
        </div>
        <input
          ref={photos}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
          multiple
          hidden
          onChange={(event) => {
            add(event.target.files)
            event.target.value = ''
          }}
        />
        {uploader.element}

        {files.length > 0 && (
          <section className="rounded-card bg-surface-container-low p-5">
            <h2 className="mb-3 text-title-medium">
              {interpolate(ngettext('%s file da leggere', '%s file da leggere', files.length), [
                files.length,
              ])}
            </h2>
            <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
              {files.map((file, index) => (
                <FileThumb
                  key={`${file.name}-${index}`}
                  file={file}
                  onRemove={() => setFiles(files.filter((_, at) => at !== index))}
                />
              ))}
            </ul>
          </section>
        )}

        <p className="flex items-start gap-2 px-1 text-body-small text-on-surface-variant">
          <Icon name="lightbulb" size={18} />
          {interpolate(
            gettext(
              'Una pagina per foto, dritta e con buona luce. Al massimo %s foto alla volta, fino a 10 MB l’una.',
            ),
            [MAX_FILES],
          )}
        </p>

        <ErrorBanner error={start.error ?? uploader.upload.error} />
        <div className="flex justify-end">
          <button
            type="button"
            className="btn-filled"
            disabled={!files.length || start.isPending}
            onClick={async () => {
              try {
                const job = await start.mutateAsync(files)
                navigate(`/ricette/importa/${job.id}`, { replace: true })
              } catch {
                // L'errore (file rifiutato, LLM non configurato) si vede sopra.
              }
            }}
          >
            <Icon name="auto_awesome" size={20} />
            {start.isPending ? gettext('Carico…') : gettext('Leggi le ricette')}
          </button>
        </div>
      </div>
    </Page>
  )
}

function FileThumb({ file, onRemove }: { file: File; onRemove: () => void }) {
  const isImage = file.type.startsWith('image/') && !/hei[cf]/.test(file.type)
  // L'URL si crea e si revoca nello stesso effetto: con StrictMode l'effetto
  // gira due volte e un URL creato fuori sarebbe gia' revocato alla seconda.
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!isImage) return
    const next = URL.createObjectURL(file)
    setUrl(next)
    return () => URL.revokeObjectURL(next)
  }, [file, isImage])
  return (
    <li className="relative">
      <div className="flex aspect-[3/4] items-center justify-center overflow-hidden rounded-row bg-surface-container-high">
        {url ? (
          <img src={url} alt="" className="h-full w-full object-cover" />
        ) : (
          <Icon
            name={file.type === 'application/pdf' ? 'picture_as_pdf' : 'image'}
            size={36}
            className="text-on-surface-variant"
          />
        )}
      </div>
      <p className="mt-1 truncate text-label-small text-on-surface-variant">{file.name}</p>
      <IconButton
        icon="close"
        label={gettext('Togli il file')}
        onClick={onRemove}
        className="absolute right-1 top-1 bg-surface text-on-surface shadow-fab"
      />
    </li>
  )
}

/* ------------------------------------------------- lavoro e revisione ---- */

export function ImportJobPage() {
  const { jobId } = useParams()
  const { data: job, error } = useJob(jobId)
  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="mb-5 flex items-center gap-3">
        <IconButton
          icon="arrow_back"
          size="md"
          label={gettext('Ricette')}
          onClick={() => history.back()}
        />
        <h1 className="flex-1 text-title-large">{gettext('Importa ricette')}</h1>
      </header>
      <ErrorBanner error={error} />
      {!job && !error && <Skeleton className="h-64 rounded-card" />}
      {job && <JobView key={`${job.id}-${job.status}`} job={job} />}
    </Page>
  )
}

function JobView({ job }: { job: Job }) {
  if (job.status === 'queued' || job.status === 'running') return <Reading job={job} />
  if (job.status === 'failed') return <Failed job={job} />
  if (job.status === 'confirmed') return <Done job={job} />
  if (!job.result.recipes?.length) return <NothingFound job={job} />
  return <Review job={job} />
}

function Reading({ job }: { job: Job }) {
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
      title={gettext('Sto leggendo le ricette…')}
      description={interpolate(
        ngettext(
          'Di solito ci vuole meno di un minuto per %s file. Puoi anche uscire: la lettura continua e la ritrovi nel ricettario.',
          'Di solito ci vuole meno di un minuto per %s file. Puoi anche uscire: la lettura continua e la ritrovi nel ricettario.',
          job.files.length,
        ),
        [job.files.length],
      )}
      action={<div className="progress-indeterminate w-48" />}
    />
  )
}

function Failed({ job }: { job: Job }) {
  const retry = useRetryJob()
  return (
    <div className="grid gap-4">
      <EmptyState
        icon="error"
        title={gettext('Non sono riuscito a leggere le ricette')}
        description={job.error}
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <DiscardButton job={job} label={gettext('Lascia perdere')} />
            <button
              type="button"
              className="btn-filled"
              disabled={retry.isPending}
              onClick={() => retry.mutate(job.id)}
            >
              <Icon name="refresh" size={20} />
              {gettext('Riprova')}
            </button>
          </div>
        }
      />
      <ErrorBanner error={retry.error} />
    </div>
  )
}

function NothingFound({ job }: { job: Job }) {
  return (
    <EmptyState
      icon="search_off"
      title={gettext('Non ho trovato ricette')}
      description={job.result.problem || gettext('Prova con una foto più nitida o un altro file.')}
      action={
        <DiscardButton job={job} label={gettext('Prova con altri file')} then="/ricette/importa" />
      }
    />
  )
}

function Done({ job }: { job: Job }) {
  const created = job.result.created ?? []
  return (
    <EmptyState
      icon="task_alt"
      title={interpolate(
        ngettext(
          '%s ricetta aggiunta al ricettario',
          '%s ricette aggiunte al ricettario',
          created.length,
        ),
        [created.length],
      )}
      action={
        <div className="flex flex-wrap justify-center gap-2">
          {created.length === 1 && (
            <Link to={`/ricette/${created[0]}`} className="btn-tonal">
              {gettext('Apri la ricetta')}
            </Link>
          )}
          <Link to="/ricette" className="btn-filled">
            <Icon name="menu_book" size={20} />
            {gettext('Vai al ricettario')}
          </Link>
        </div>
      }
    />
  )
}

function DiscardButton({
  job,
  label,
  then = '/ricette',
}: {
  job: Job
  label: string
  then?: string
}) {
  const navigate = useNavigate()
  const discard = useDiscardJob()
  return (
    <button
      type="button"
      className="btn-outlined"
      disabled={discard.isPending}
      onClick={async () => {
        await discard.mutateAsync(job.id)
        navigate(then, { replace: true })
      }}
    >
      {label}
    </button>
  )
}

interface Item {
  draft: Draft
  include: boolean
  inferred: string[]
}

/** Le bozze lette, una card per ricetta: si correggono, si tengono o si scartano. */
function Review({ job }: { job: Job }) {
  const navigate = useNavigate()
  const confirm = useConfirm()
  const save = useConfirmImport()
  const discard = useDiscardJob()
  const [items, setItems] = useState<Item[]>(() =>
    (job.result.recipes ?? []).map((recipe) => ({
      draft: draftFromImport(recipe),
      include: true,
      inferred: recipe.inferred,
    })),
  )
  const [open, setOpen] = useState(0)
  const kept = items.filter((item) => item.include)
  const missingTitle = kept.some((item) => !item.draft.title.trim())
  const errors = recipeErrors(save.error, items)

  const update = (index: number, changes: Partial<Item>) =>
    setItems((current) =>
      current.map((item, at) => (at === index ? { ...item, ...changes } : item)),
    )

  return (
    <div className="grid gap-4">
      <section className="rounded-card bg-surface-container-low p-5">
        <h2 className="text-title-large">
          {interpolate(ngettext('Ho trovato %s ricetta', 'Ho trovato %s ricette', items.length), [
            items.length,
          ])}
        </h2>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          {gettext(
            'Controlla e correggi prima di aggiungerle. Quello che il testo non diceva l’ho stimato io: lo trovi segnato come',
          )}{' '}
          <span className="inline-flex items-center gap-1 rounded-pill bg-tertiary-container px-2 py-0.5 text-label-small text-on-tertiary-container">
            <Icon name="auto_awesome" size={14} />
            {gettext('Dedotto')}
          </span>
        </p>
      </section>

      {items.map((item, index) => (
        <section
          key={index}
          className={clsx(
            'overflow-hidden rounded-card border-2 transition-colors',
            item.include ? 'border-primary-container' : 'border-transparent opacity-70',
          )}
        >
          <header className="flex items-center gap-3 bg-surface-container-low px-5 py-3">
            <button
              type="button"
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
              onClick={() => setOpen(open === index ? -1 : index)}
              aria-expanded={open === index}
            >
              <Icon name={open === index ? 'expand_less' : 'expand_more'} size={24} />
              <span className="min-w-0">
                <span className="block truncate text-body-large font-medium">
                  {item.draft.title || gettext('Senza nome')}
                </span>
                <span className="block text-body-small text-on-surface-variant">
                  {interpolate(
                    ngettext('%s ingrediente', '%s ingredienti', item.draft.lines.length),
                    [item.draft.lines.length],
                  )}
                  {errors[index] && (
                    <span className="ml-2 text-error">{gettext('Da correggere')}</span>
                  )}
                </span>
              </span>
            </button>
            <Switch
              label={gettext('Aggiungi questa ricetta')}
              checked={item.include}
              onChange={(include) => update(index, { include })}
            />
          </header>
          {open === index && item.include && (
            <div className="bg-surface p-3 sm:p-5">
              <RecipeEditor
                draft={item.draft}
                setDraft={(change) =>
                  setItems((current) =>
                    current.map((other, at) =>
                      at === index
                        ? {
                            ...other,
                            draft: typeof change === 'function' ? change(other.draft) : change,
                          }
                        : other,
                    ),
                  )
                }
                errors={errors[index] ?? {}}
                inferred={item.inferred}
              />
            </div>
          )}
        </section>
      ))}

      <ErrorBanner error={save.error} />
      <div className="flex flex-wrap justify-end gap-2">
        <button
          type="button"
          className="btn-text text-error"
          disabled={discard.isPending}
          onClick={async () => {
            const ok = await confirm({
              title: gettext('Scartare tutto?'),
              message: gettext('Le ricette lette e i file caricati spariscono.'),
              confirmLabel: gettext('Scarta'),
              icon: 'delete',
              destructive: true,
            })
            if (!ok) return
            await discard.mutateAsync(job.id)
            navigate('/ricette', { replace: true })
          }}
        >
          {gettext('Scarta tutto')}
        </button>
        <button
          type="button"
          className="btn-filled"
          disabled={!kept.length || missingTitle || save.isPending}
          onClick={() =>
            save.mutate({ id: job.id, recipes: kept.map((item) => payloadFrom(item.draft)) })
          }
        >
          <Icon name="playlist_add_check" size={20} />
          {interpolate(ngettext('Aggiungi %s ricetta', 'Aggiungi %s ricette', kept.length), [
            kept.length,
          ])}
        </button>
      </div>
    </div>
  )
}

/**
 * Gli errori della conferma, per ricetta: il server risponde con
 * `{recipes: [{title: [...]}, {}]}` nell'ordine delle ricette tenute.
 */
function recipeErrors(error: unknown, items: Item[]): Record<number, Record<string, string>> {
  if (!(error instanceof ApiError) || !error.data || typeof error.data !== 'object') return {}
  const list = (error.data as { recipes?: unknown }).recipes
  if (!Array.isArray(list)) return {}
  const keptIndexes = items.flatMap((item, index) => (item.include ? [index] : []))
  const out: Record<number, Record<string, string>> = {}
  list.forEach((entry, position) => {
    if (!entry || typeof entry !== 'object' || !Object.keys(entry).length) return
    const fields: Record<string, string> = {}
    for (const [key, value] of Object.entries(entry as Record<string, unknown>)) {
      fields[key] = Array.isArray(value) ? String(value[0]) : String(value)
    }
    out[keptIndexes[position]] = fields
  })
  return out
}
