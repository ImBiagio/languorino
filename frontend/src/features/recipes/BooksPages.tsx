// Ricettari PDF (ADR 0006): un PDF lungo si legge a pezzi e diventa una
// biblioteca di ricette da sfogliare; nel proprio ricettario entra solo quello
// che si salva.

import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate, useParams } from 'react-router-dom'

import {
  useBook,
  useBooks,
  useDeleteBook,
  useRecipes,
  useRenameBook,
  useBookImages,
  useRetryBook,
  useUploadBook,
} from '../../api/hooks'
import { useConfirm } from '../../components/ConfirmDialog'
import { Page, PageHeader } from '../../components/Layout'
import { CookbookIllustration, FoodPattern } from '../../components/illustrations'
import {
  EmptyState,
  ErrorBanner,
  Field,
  Icon,
  IconButton,
  Modal,
  Progress,
  Skeleton,
} from '../../components/ui'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { RecipeBook } from '../../lib/types'
import { RecipeCard } from './RecipesPage'

/** Le due schede della sezione Ricette: il proprio ricettario e i PDF. */
export function RecipeTabs() {
  const tab = (to: string, icon: string, label: string, end?: boolean) => (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        clsx(
          'state relative flex flex-1 items-center justify-center gap-2 px-4 pb-3 pt-2 text-body-large font-medium sm:flex-none',
          isActive ? 'text-primary' : 'text-on-surface-variant',
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon name={icon} size={20} filled={isActive} />
          {label}
          {isActive && (
            <span className="absolute inset-x-4 bottom-0 h-[3px] rounded-t-pill bg-primary" />
          )}
        </>
      )}
    </NavLink>
  )
  return (
    <nav className="flex border-b border-outline-variant">
      {tab('/ricette', 'menu_book', gettext('Il mio ricettario'), true)}
      {tab('/ricette/ricettari', 'library_books', gettext('Ricettari PDF'))}
    </nav>
  )
}

/** Il caricamento di un PDF come ricettario: input nascosto + mutazione. */
export function useBookUploader() {
  const navigate = useNavigate()
  const upload = useUploadBook()
  const input = useRef<HTMLInputElement>(null)
  const element = (
    <input
      ref={input}
      type="file"
      accept="application/pdf"
      hidden
      onChange={async (event) => {
        const file = event.target.files?.[0]
        event.target.value = ''
        if (!file) return
        try {
          const book = await upload.mutateAsync(file)
          navigate(`/ricette/ricettari/${book.id}`)
        } catch {
          // L'errore (non e' un PDF, troppe pagine, LLM spento) si vede in pagina.
        }
      }}
    />
  )
  return { open: () => input.current?.click(), element, upload }
}

/* -------------------------------------------------------------- elenco ---- */

export function BooksPage() {
  const { data: books, error, isPending } = useBooks()
  const uploader = useBookUploader()

  return (
    <Page>
      <PageHeader title={gettext('Ricette')} subtitle={gettext('Ricettari in PDF da sfogliare')} />
      <div className="grid gap-4 px-5 md:px-8">
        <RecipeTabs />
        {uploader.element}

        <section className="relative overflow-hidden rounded-panel bg-primary-container p-6 text-on-primary-container">
          <div className="absolute inset-y-0 right-0 w-1/2 [mask-image:linear-gradient(to_right,transparent,black)]">
            <FoodPattern opacity={0.6} />
          </div>
          <div className="relative max-w-xl">
            <h2 className="text-title-large">
              {gettext('Un ricettario intero, pagina per pagina')}
            </h2>
            <p className="mt-1 text-body-large">
              {gettext(
                'Carica il PDF del nutrizionista o un ricettario: lo leggo a pezzi e trovi tutte le ricette qui. Nel tuo ricettario metti solo quelle che vuoi.',
              )}
            </p>
            <button
              type="button"
              className="btn-filled mt-4"
              disabled={uploader.upload.isPending}
              onClick={uploader.open}
            >
              <Icon name="upload_file" size={20} />
              {uploader.upload.isPending ? gettext('Carico…') : gettext('Carica un PDF')}
            </button>
          </div>
        </section>
        <ErrorBanner error={uploader.upload.error ?? error} />

        {isPending && <Skeleton className="h-24 rounded-card" />}
        {books && books.length === 0 && (
          <EmptyState
            illustration={<CookbookIllustration />}
            title={gettext('Ancora nessun ricettario')}
            description={gettext('Fino a 200 pagine e 50 MB per PDF.')}
          />
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          {books?.map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
        </div>
      </div>
    </Page>
  )
}

function BookCard({ book }: { book: RecipeBook }) {
  return (
    <Link
      to={`/ricette/ricettari/${book.id}`}
      className="state card-elevated flex items-start gap-4 bg-surface-container-low p-4"
    >
      <span className="flex h-14 w-11 shrink-0 items-center justify-center rounded-[10px] bg-accent text-white shadow-fab">
        <Icon name="picture_as_pdf" size={26} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-body-large font-medium">{book.title}</span>
        <BookStatusLine book={book} />
      </span>
      <Icon name="chevron_right" size={22} className="mt-1 text-on-surface-variant" />
    </Link>
  )
}

/** "12 ricette · 3 nel tuo ricettario", o l'avanzamento della lettura. */
function BookStatusLine({ book }: { book: RecipeBook }) {
  const reading = book.status === 'queued' || book.status === 'reading'
  return (
    <span className="mt-1 block text-body-small text-on-surface-variant">
      {reading && (
        <>
          <span className="block">
            {interpolate(gettext('Leggo… pagina %s di %s'), [
              Math.min(book.pages_done + 1, book.page_count),
              book.page_count,
            ])}
            {book.recipe_count > 0 &&
              ` · ${interpolate(ngettext('%s ricetta', '%s ricette', book.recipe_count), [book.recipe_count])}`}
          </span>
          {book.error && (
            <span className="mt-1 flex items-center gap-1 text-on-surface-variant">
              <Icon name="pause_circle" size={16} />
              {gettext('In pausa: Gemini è sovraccarico, riprovo da solo tra qualche minuto.')}
            </span>
          )}
          <span className="mt-2 block">
            <Progress value={book.pages_done} max={book.page_count} label={gettext('Lettura')} />
          </span>
        </>
      )}
      {book.status === 'failed' && (
        <span className="text-error">
          {interpolate(gettext('Interrotto a pagina %s di %s'), [book.pages_done, book.page_count])}
        </span>
      )}
      {book.status === 'ready' && (
        <>
          {interpolate(ngettext('%s ricetta', '%s ricette', book.recipe_count), [
            book.recipe_count,
          ])}
          {' · '}
          {interpolate(ngettext('%s pagina', '%s pagine', book.page_count), [book.page_count])}
          {book.saved_count > 0 &&
            ` · ${interpolate(
              ngettext('%s nel tuo ricettario', '%s nel tuo ricettario', book.saved_count),
              [book.saved_count],
            )}`}
        </>
      )}
    </span>
  )
}

/* ------------------------------------------------------------ dettaglio ---- */

export function BookPage() {
  const { bookId } = useParams()
  const navigate = useNavigate()
  const confirm = useConfirm()
  const { data: book, error } = useBook(bookId)
  const retry = useRetryBook()
  const remove = useDeleteBook()
  const [renaming, setRenaming] = useState(false)
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(text.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [text])
  const reading = book?.status === 'queued' || book?.status === 'reading'
  const drawing = book?.images_status === 'searching' || book?.images_status === 'drawing'
  const { data: recipes } = useRecipes({ book: bookId, q: query }, { poll: reading || drawing })

  if (error) {
    return (
      <Page className="px-5 pt-5 md:px-8 md:pt-8">
        <ErrorBanner error={error} />
      </Page>
    )
  }
  if (!book) return <Skeleton className="m-5 h-40 rounded-card md:m-8" />

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="mb-4 flex items-center gap-2">
        <IconButton
          icon="arrow_back"
          size="md"
          label={gettext('Ricettari PDF')}
          onClick={() => navigate('/ricette/ricettari')}
        />
        <h1 className="min-w-0 flex-1 truncate text-title-large">{book.title}</h1>
        <IconButton
          icon="edit"
          size="md"
          label={gettext('Rinomina')}
          onClick={() => setRenaming(true)}
        />
        <IconButton
          icon="delete"
          size="md"
          label={gettext('Elimina il ricettario')}
          className="text-error"
          onClick={async () => {
            const ok = await confirm({
              title: gettext('Eliminare il ricettario?'),
              message: gettext(
                'Spariscono il PDF e le sue ricette. Quelle che hai salvato nel tuo ricettario restano.',
              ),
              confirmLabel: gettext('Elimina'),
              icon: 'delete',
              destructive: true,
            })
            if (!ok) return
            await remove.mutateAsync(book.id)
            navigate('/ricette/ricettari', { replace: true })
          }}
        />
      </header>

      <div className="grid gap-4">
        <section className="rounded-card bg-surface-container-low p-4">
          <BookStatusLine book={book} />
          {book.status === 'failed' && (
            <div className="mt-3 grid gap-3">
              <ErrorBanner error={book.error || gettext('La lettura si è interrotta.')} />
              <button
                type="button"
                className="btn-filled w-fit"
                disabled={retry.isPending}
                onClick={() => retry.mutate(book.id)}
              >
                <Icon name="refresh" size={20} />
                {interpolate(gettext('Riprendi da pagina %s'), [book.pages_done + 1])}
              </button>
              <ErrorBanner error={retry.error} />
            </div>
          )}
        </section>
        {book.status === 'ready' && book.recipe_count > 0 && <BookImages book={book} />}

        <label className="flex items-center gap-3 rounded-pill bg-surface-container-high px-5 py-3 focus-within:ring-2 focus-within:ring-primary">
          <Icon name="search" size={22} className="text-on-surface-variant" />
          <input
            className="min-w-0 flex-1 bg-transparent text-body-large outline-none placeholder:text-on-surface-variant"
            placeholder={gettext('Cerca in questo ricettario')}
            value={text}
            onChange={(event) => setText(event.target.value)}
            type="search"
          />
        </label>

        {recipes && recipes.results.length === 0 && (
          <EmptyState
            icon={reading ? 'hourglass_top' : 'search_off'}
            title={
              reading
                ? gettext('Le ricette arrivano man mano che leggo')
                : query
                  ? gettext('Nessuna ricetta trovata')
                  : gettext('Non ho trovato ricette in questo PDF')
            }
          />
        )}
        {recipes && recipes.results.length > 0 && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {recipes.results.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} showSaved />
            ))}
          </div>
        )}
      </div>

      {renaming && <RenameDialog book={book} onClose={() => setRenaming(false)} />}
    </Page>
  )
}

/** Foto delle ricette dal PDF e illustrazioni per le altre (ADR 0015). */
function BookImages({ book }: { book: RecipeBook }) {
  const start = useBookImages()
  const status = book.images_status
  const working = status === 'searching' || status === 'drawing'
  const missing = book.without_image
  return (
    <section className="grid gap-3 rounded-card bg-surface-container-low p-4">
      <div className="flex items-start gap-3">
        <Icon
          name={working ? 'hourglass_top' : 'imagesmode'}
          size={22}
          className={clsx('mt-0.5 text-primary', working && 'animate-pulse')}
        />
        <div className="min-w-0 flex-1">
          <p className="text-body-large font-medium">{gettext('Immagini delle ricette')}</p>
          <p className="text-body-small text-on-surface-variant">
            {status === 'searching'
              ? interpolate(gettext('Cerco le foto nel PDF: pagina %s di %s…'), [
                  book.images_pages_done,
                  book.page_count,
                ])
              : status === 'drawing'
                ? interpolate(
                    ngettext(
                      'Disegno le ricette senza foto: ne manca %s.',
                      'Disegno le ricette senza foto: ne mancano %s.',
                      missing,
                    ),
                    [missing],
                  )
                : status === ''
                  ? gettext(
                      'Prendo le foto dei piatti dal PDF, se ci sono; le altre ricette le faccio disegnare in modo semplice.',
                    )
                  : missing
                    ? interpolate(
                        ngettext(
                          'Foto trovate nel PDF: %s. Senza immagine: %s ricetta.',
                          'Foto trovate nel PDF: %s. Senza immagine: %s ricette.',
                          missing,
                        ),
                        [book.images_found, missing],
                      )
                    : interpolate(
                        gettext('Foto trovate nel PDF: %s. Tutte le ricette hanno un’immagine.'),
                        [book.images_found],
                      )}
          </p>
        </div>
      </div>
      {book.images_error && (
        <p
          className={clsx(
            'rounded-row px-3 py-2 text-body-small',
            status === 'failed'
              ? 'bg-error-container text-on-error-container'
              : 'bg-surface-container-high text-on-surface-variant',
          )}
        >
          {book.images_error}
        </p>
      )}
      {!working && (status === '' || status === 'failed' || missing > 0) && (
        <button
          type="button"
          className="btn-tonal w-fit"
          disabled={start.isPending}
          onClick={() => start.mutate(book.id)}
        >
          <Icon name={status === '' ? 'imagesmode' : 'refresh'} size={20} />
          {status === '' ? gettext('Cerca le foto e disegna le altre') : gettext('Riprova')}
        </button>
      )}
      <ErrorBanner error={start.error} />
    </section>
  )
}

function RenameDialog({ book, onClose }: { book: RecipeBook; onClose: () => void }) {
  const rename = useRenameBook()
  const [title, setTitle] = useState(book.title)
  return (
    <Modal open onClose={onClose} title={gettext('Rinomina il ricettario')}>
      <form
        className="grid gap-4"
        onSubmit={async (event) => {
          event.preventDefault()
          try {
            await rename.mutateAsync({ id: book.id, title })
            onClose()
          } catch {
            // L'errore si vede sotto.
          }
        }}
      >
        <Field label={gettext('Nome')}>
          <input
            className="field-input"
            value={title}
            maxLength={120}
            autoFocus
            onChange={(event) => setTitle(event.target.value)}
          />
        </Field>
        <ErrorBanner error={rename.error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-text" onClick={onClose}>
            {gettext('Annulla')}
          </button>
          <button className="btn-filled" disabled={!title.trim() || rename.isPending}>
            {gettext('Salva')}
          </button>
        </div>
      </form>
    </Modal>
  )
}
